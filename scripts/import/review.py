"""
scripts/import/review.py — review over `candidate`, writing only to
`decision` (tasks 6.1-6.4, design D1; import-review-web tasks 2.1-2.2).

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

The terminal loop (`run_interactive`) and its `[e]dit` branch are gone
(import-review-web design D4/D1) — `scripts/import/web.py` is the only
front end over these functions now, and review is pure triage: no action
here ever writes `edited_fields_json`."""

from __future__ import annotations

import datetime
import json
import math
import sqlite3
from pathlib import Path

import merge as merge_stage

NO_SIGNAL_INTERLEAVE_BASELINE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "import" / "no_signal_interleave_baseline.json"
)


def queue(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every importable candidate, ordered by the review ordering key
    (tasks 5.5, 6.1)."""
    rows = conn.execute("SELECT * FROM candidate WHERE verdict = 'import'").fetchall()
    return sorted(rows, key=lambda row: merge_stage.order_sort_key(json.loads(row["order_key_json"])))


def decided_signature_keys(conn: sqlite3.Connection) -> set[str]:
    return {row["signature_key"] for row in conn.execute("SELECT signature_key FROM decision").fetchall()}


def _note_type(row: sqlite3.Row) -> str | None:
    return json.loads(row["fields_json"]).get("note_type")


def _has_order_signal(row: sqlite3.Row) -> bool:
    """Same "has any ranking signal" test `merge.order_sort_key` uses to
    decide whether a candidate sorts in a real tier or in the final
    "no signal sorts last" tier (design D7) — reused here rather than
    reimplemented, so the two can't drift apart. Not just `listening`:
    measured against the live store, 255 `word` and 97 `expression`
    candidates ALSO carry no signal (no `freq6k`/`core6k`/CEFR/chapter
    data reached them), and fall into the exact same tail."""
    order_key = json.loads(row["order_key_json"])
    return bool(
        order_key.get("frequency_index") is not None
        or order_key.get("core6k_rank") is not None
        or order_key.get("cefr")
        or order_key.get("chapter")
    )


def _signaled_and_unsignaled_counts(conn: sqlite3.Connection) -> tuple[int, int, int, int]:
    """(signaled_total, unsignaled_total, decided_signaled, decided_unsignaled)
    over the whole queue (task 6.1's `verdict == 'import'` set)."""
    full = queue(conn)
    decided = decided_signature_keys(conn)
    signaled_total = unsignaled_total = decided_signaled = decided_unsignaled = 0
    for row in full:
        has_signal = _has_order_signal(row)
        is_decided = row["signature_key"] in decided
        if has_signal:
            signaled_total += 1
            decided_signaled += is_decided
        else:
            unsignaled_total += 1
            decided_unsignaled += is_decided
    return signaled_total, unsignaled_total, decided_signaled, decided_unsignaled


def _load_or_create_no_signal_interleave_baseline(conn: sqlite3.Connection) -> dict:
    """Operator decision (2026-11-09, generalised from an initial
    `listening`-only fix the same day): any candidate with no ranking
    signal at all — not just `listening` (`frequency_index`/`core6k_rank`
    only ever attach to word-sourced rows), but also the `word`/
    `expression` candidates `freq6k`/`core6k`/CEFR/chapter data never
    reached — falls entirely into `order_sort_key`'s own "no signal sorts
    last" tier and clusters at the very tail. Measured against the live
    store: the no-signal tier didn't start until position 5,214 of
    6,973, and held 1,407 `listening` + 255 `word` + 97 `expression`
    candidates — which is why 2,500 reviews in, the operator had not seen
    a single `listening` candidate, and wouldn't have hit most of these
    others either.

    A snapshot of where review stood *the first time this feature ran*:
    how many signaled and unsignaled candidates were already decided, and
    the ratio of what's left of each. Written once, to
    `import/no_signal_interleave_baseline.json` (same convention as
    `baseline_eligibility.json`), and never updated after — this is the
    anchor an "overdue" check (`unsignaled_candidate_is_due`) measures
    progress *since*, so the fix only affects reviewing from here
    forward, never retroactively treats the operator's existing decided
    candidates as a backlog of "owed" cards to dump all at once."""
    if NO_SIGNAL_INTERLEAVE_BASELINE_PATH.exists():
        return json.loads(NO_SIGNAL_INTERLEAVE_BASELINE_PATH.read_text(encoding="utf-8"))

    signaled_total, unsignaled_total, decided_signaled, decided_unsignaled = _signaled_and_unsignaled_counts(conn)
    signaled_remaining = signaled_total - decided_signaled
    unsignaled_remaining = unsignaled_total - decided_unsignaled
    baseline = {
        "decided_signaled_at_baseline": decided_signaled,
        "decided_unsignaled_at_baseline": decided_unsignaled,
        "target_ratio": unsignaled_remaining / signaled_remaining if signaled_remaining else 0.0,
    }
    NO_SIGNAL_INTERLEAVE_BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    NO_SIGNAL_INTERLEAVE_BASELINE_PATH.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    return baseline


def unsignaled_candidate_is_due(conn: sqlite3.Connection) -> bool:
    """Whether the signaled decisions made *since the baseline* have
    outpaced the unsignaled decisions made since the same baseline,
    relative to `target_ratio` — i.e. whether an unsignaled candidate
    (`listening`, or a `word`/`expression` with no ranking data) is now
    overdue and should be surfaced immediately.

    Deliberately NOT a position-counting loop over the current undecided
    array (the first attempt at this, found broken by direct observation:
    recomputing a stride-based insertion index fresh from array-index 0
    on every single call is a treadmill — each decision only ever strips
    exactly one item from the front, so "the next unsignaled candidate is
    always ~3 items away" stays true forever, no matter how many
    decisions happen, because the count never actually advances toward
    it). This instead compares two *monotonically increasing* counters —
    decided-signaled-count and decided-unsignaled-count, both backed by
    `decision`, which never resets or rewinds — so "how overdue are we"
    only ever moves in the right direction, and resolves to exactly 0 the
    moment the operator actually decides the overdue candidate (rather
    than merely being shown it)."""
    baseline = _load_or_create_no_signal_interleave_baseline(conn)
    _, _, decided_signaled_now, decided_unsignaled_now = _signaled_and_unsignaled_counts(conn)
    signaled_progress = decided_signaled_now - baseline["decided_signaled_at_baseline"]
    unsignaled_progress = decided_unsignaled_now - baseline["decided_unsignaled_at_baseline"]
    target_unsignaled_by_now = math.floor(signaled_progress * baseline["target_ratio"])
    return target_unsignaled_by_now > unsignaled_progress


def _round_robin_by_note_type(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    """Proportionally interleaves `rows` by `note_type` — measured need:
    of the no-signal pool, `listening` outnumbers `word`/`expression`
    roughly 4-to-1, but `queue`'s stable sort leaves them in whatever
    order the underlying SQL happened to return (effectively source-
    insertion order), which clusters almost all `word`/`expression`
    before any `listening` — so taking element 0 of the raw no-signal
    list repeatedly exhausted ~350 `word`/`expression` candidates before
    a single `listening` one appeared. Picks, at each step, whichever
    type's consumed-so-far fraction is lowest — a standard proportional-
    apportionment technique — so types stay mixed throughout rather than
    one exhausting before another starts. Recomputed fresh each call,
    always read from position 0 by the caller, so (unlike a stride/
    threshold scheme) there is nothing here to treadmill: it only decides
    *which* currently-undecided candidate is "first," never counts steps
    toward a future one."""
    buckets: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        buckets.setdefault(_note_type(row), []).append(row)
    if len(buckets) <= 1:
        return rows

    indices = {note_type: 0 for note_type in buckets}
    result: list[sqlite3.Row] = []
    for _ in range(len(rows)):
        note_type = min(
            (nt for nt, bucket in buckets.items() if indices[nt] < len(bucket)),
            key=lambda nt: (indices[nt] + 1) / len(buckets[nt]),
        )
        result.append(buckets[note_type][indices[note_type]])
        indices[note_type] += 1
    return result


def pending_queue(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """The queue minus whatever already has a decision — reopening review
    resumes here (task 6.4). When an unsignaled candidate is overdue
    (`unsignaled_candidate_is_due`), the next undecided one is surfaced as
    the very first entry — forcing it to be the actual next card shown,
    not merely present somewhere further down an array the operator may
    never reach before the next recompute (see that function's
    docstring). Deliberately applied only here, never to the underlying
    `order_key_json` persisted by `merge` or to `push`'s ordering (design
    D6): this changes what the operator is shown next, never the
    permanent push order a card's `Cards[]` introduction order depends
    on."""
    decided = decided_signature_keys(conn)
    undecided = [row for row in queue(conn) if row["signature_key"] not in decided]
    unsignaled = _round_robin_by_note_type([row for row in undecided if not _has_order_signal(row)])
    signaled = [row for row in undecided if _has_order_signal(row)]
    if not unsignaled or not signaled:
        return undecided
    if unsignaled_candidate_is_due(conn):
        return [unsignaled[0], *signaled, *unsignaled[1:]]
    return [*signaled, *unsignaled]


def progress(conn: sqlite3.Connection) -> tuple[int, int]:
    """(reviewed, remaining) over the accept/reject queue (task 6.4)."""
    all_in_queue = {row["signature_key"] for row in queue(conn)}
    reviewed = len(all_in_queue & decided_signature_keys(conn))
    return reviewed, len(all_in_queue) - reviewed


def record_decision(conn: sqlite3.Connection, signature_key: str, decision: str) -> None:
    """`decision` is `"accept"` or `"reject"`. Writes only to `decision`
    (task 6.3), upserting so re-reviewing a candidate replaces its own
    prior decision without touching anyone else's.

    Takes no `edited_fields` — review is triage only (design D4, task
    3.4); `edited_fields_json` stays in the schema but no caller of this
    function can write to it."""
    if decision not in ("accept", "reject"):
        raise ValueError(f"decision must be 'accept' or 'reject', got {decision!r}")
    decided_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO decision (signature_key, decision, edited_fields_json, decided_at)
        VALUES (?, ?, NULL, ?)
        ON CONFLICT(signature_key) DO UPDATE SET
            decision = excluded.decision,
            edited_fields_json = NULL,
            decided_at = excluded.decided_at
        """,
        (signature_key, decision, decided_at),
    )
    conn.commit()


def undo_last_decision(conn: sqlite3.Connection) -> str | None:
    """Reverses the most recently made decision (design D5, task 3.6),
    deleting it so the candidate re-enters `pending_queue`. Returns the
    undone signature_key, or None if there is nothing to undo.

    Repeated calls step back one further each time — `decided_at` strictly
    orders each decision, with `id` as a tie-breaker since the timestamp's
    resolution can't distinguish two decisions recorded in the same
    instant."""
    row = conn.execute("SELECT signature_key FROM decision ORDER BY decided_at DESC, id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM decision WHERE signature_key = ?", (row["signature_key"],))
    conn.commit()
    return row["signature_key"]


def recent_decisions(conn: sqlite3.Connection, limit: int = 6) -> list[sqlite3.Row]:
    """The most recently made decisions, newest first (design D5's "keep
    the last several visible" requirement) — joined against `candidate` so
    the UI can show what was decided, not just a bare signature key."""
    return conn.execute(
        """
        SELECT d.signature_key, d.decision, d.decided_at, c.fields_json
        FROM decision d
        JOIN candidate c ON c.signature_key = d.signature_key
        ORDER BY d.decided_at DESC, d.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


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


def run(conn: sqlite3.Connection, run_id: int, host: str = "127.0.0.1", port: int = 5057) -> tuple[int, int, int]:
    """Stage entrypoint (task 2.2). Unlike the other stages, `review` has
    no entry in `store.STAGE_OUTPUT_TABLE` — it never replaces a table
    wholesale, only appends/upserts into `decision` (task 1.5's own
    documented exception).

    Launches `web.py`'s localhost Flask server and blocks until the
    operator stops it (Ctrl+C) — there is no terminal loop any more
    (import-review-web design D1/D4); every decision is written by the
    server's own routes via `record_decision` as the operator reviews."""
    import web

    total_queue = len(queue(conn))
    reviewed_before, _ = progress(conn)

    app = web.create_app(conn)
    print(f"review: {total_queue} in queue, {reviewed_before} already reviewed")
    print(f"review: open http://{host}:{port}")
    try:
        # threaded=False: one request at a time, so the single sqlite3
        # connection this module shares across routes is never touched
        # concurrently even with check_same_thread relaxed for it.
        app.run(host=host, port=port, threaded=False)
    except KeyboardInterrupt:
        pass

    reviewed_after, _ = progress(conn)
    return total_queue, reviewed_after - reviewed_before, 0
