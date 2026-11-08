"""
scripts/import/review.py — section 6: interactive accept/reject/edit over
`candidate`, writing only to `decision` (tasks 6.1-6.4, design D1).

Local to this tool, not the stabbur UI (design D1) — the operator reviews
candidates *before* they become notes; putting review in stabbur's own UI
would mean treating undecided proposals as notes, which is exactly the
lifecycle mismatch D1 rejects.

The review queue is every candidate with `verdict == "import"` (task 6.1),
ordered by `merge.order_sort_key` (task 5.5/design D7). Auto-skipped
candidates (`verdict == "skip"`) are not part of this queue — they were
never going to be pushed — but remain queryable directly from `candidate`
for the task 4.8 skipped-set spot-check, which stays in force under D13.

Decisions are written only to `decision`, keyed by signature, never to
`candidate` (task 6.3) — this is the payoff of design D2/task 1.3: judge
and merge can be re-run after a known-set or priority fix without losing
review. Resuming re-derives the queue position from what's already in
`decision` rather than storing a separate cursor (task 6.4).
"""

from __future__ import annotations

import datetime
import json
import sqlite3

import merge as merge_stage


def queue(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every importable candidate, ordered by the review ordering key
    (tasks 5.5, 6.1)."""
    rows = conn.execute("SELECT * FROM candidate WHERE verdict = 'import'").fetchall()
    return sorted(rows, key=lambda row: merge_stage.order_sort_key(json.loads(row["order_key_json"])))


def decided_signature_keys(conn: sqlite3.Connection) -> set[str]:
    return {row["signature_key"] for row in conn.execute("SELECT signature_key FROM decision").fetchall()}


def pending_queue(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """The queue minus whatever already has a decision — reopening review
    resumes here (task 6.4)."""
    decided = decided_signature_keys(conn)
    return [row for row in queue(conn) if row["signature_key"] not in decided]


def progress(conn: sqlite3.Connection) -> tuple[int, int]:
    """(reviewed, remaining) over the accept/reject queue (task 6.4)."""
    all_in_queue = {row["signature_key"] for row in queue(conn)}
    reviewed = len(all_in_queue & decided_signature_keys(conn))
    return reviewed, len(all_in_queue) - reviewed


def record_decision(
    conn: sqlite3.Connection, signature_key: str, decision: str, edited_fields: dict | None = None
) -> None:
    """`decision` is `"accept"` or `"reject"`. Writes only to `decision`
    (task 6.3), upserting so re-reviewing a candidate replaces its own
    prior decision without touching anyone else's."""
    if decision not in ("accept", "reject"):
        raise ValueError(f"decision must be 'accept' or 'reject', got {decision!r}")
    decided_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO decision (signature_key, decision, edited_fields_json, decided_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(signature_key) DO UPDATE SET
            decision = excluded.decision,
            edited_fields_json = excluded.edited_fields_json,
            decided_at = excluded.decided_at
        """,
        (signature_key, decision, json.dumps(edited_fields, ensure_ascii=False) if edited_fields else None, decided_at),
    )
    conn.commit()


def format_candidate(row: sqlite3.Row) -> str:
    """Task 6.2: merged fields with source attribution, conflicts, verdict
    + evidence, the stock relative when flagged, and whether human audio
    is attached."""
    fields = json.loads(row["fields_json"])
    sources = json.loads(row["sources_json"])
    conflicts = json.loads(row["conflicts_json"])
    evidence = json.loads(row["verdict_evidence_json"])

    lines = [
        f"signature: {row['signature_key']}",
        f"verdict: {row['verdict']}" + (f" ({evidence['rule']})" if evidence.get("rule") else ""),
    ]
    for field, value in fields.items():
        lines.append(f"  {field}: {value!r}  [{sources.get(field, '?')}]")
    if conflicts:
        lines.append("  conflicts:")
        for field, losers in conflicts.items():
            for loser in losers:
                lines.append(f"    {field}: {loser['source']} also has {loser['value']!r}")
    if evidence.get("cf_stock"):
        lines.append(f"  cf. stock: {evidence['cf_stock']}")
    if evidence.get("tokens"):
        lines.append(f"  all tokens known, phrase itself isn't: {evidence['tokens']}")
    lines.append(f"  audio: {'yes' if fields.get('audio_ref') else 'no'}")
    return "\n".join(lines)


def run_interactive(conn: sqlite3.Connection, input_fn=input, print_fn=print) -> int:
    """Drives the terminal review loop. Returns the number of decisions
    recorded this session. `input_fn`/`print_fn` are overridable for
    scripted/non-interactive use (e.g. a future batch-review helper), not
    for unit testing — the pure functions above cover that."""
    pending = pending_queue(conn)
    reviewed, remaining = progress(conn)
    print_fn(f"review: {reviewed} reviewed, {remaining} remaining")

    recorded = 0
    for row in pending:
        print_fn(format_candidate(row))
        choice = input_fn("[a]ccept / [r]eject / [e]dit then accept / [s]kip for now / [q]uit: ").strip().lower()
        if choice == "q":
            break
        if choice == "a":
            record_decision(conn, row["signature_key"], "accept")
            recorded += 1
        elif choice == "r":
            record_decision(conn, row["signature_key"], "reject")
            recorded += 1
        elif choice == "e":
            edited_fields = {}
            while True:
                field = input_fn("field to edit (blank to finish): ").strip()
                if not field:
                    break
                edited_fields[field] = input_fn(f"new value for {field!r}: ").strip()
            record_decision(conn, row["signature_key"], "accept", edited_fields=edited_fields or None)
            recorded += 1
        # anything else (including 's'): leave undecided, move to the next
    return recorded


def run(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Stage entrypoint. Unlike the other stages, `review` has no entry in
    `store.STAGE_OUTPUT_TABLE` — it never replaces a table wholesale, only
    appends/upserts into `decision` (task 1.5's own documented exception)."""
    total_queue = len(queue(conn))
    recorded = run_interactive(conn)
    return total_queue, recorded, 0
