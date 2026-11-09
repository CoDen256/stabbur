"""
scripts/import/audit.py — review-queue-filters section 5 (design D5): the
before/after review-eligibility report, and the recovery path (tasks
5.1-5.6).

The deliverable of this change, not a side effect (design D5): this change
removes ~833 candidates from the operator's sight on heuristics with
measured but imperfect precision, and the pattern across this whole
pipeline has been that the operator finds the bugs by reading output. So
the report is grouped by rule, with text and gloss, so a wrong skip stands
out the way `bil`/`bo`/`by` did (task 5.3) — never an undifferentiated
dump.

Diffs task 1.1/1.2's `baseline_eligibility.json` (captured *before* any rule
in this change existed) against the current `candidate` table. The
disagreements section (task 5.4) and the sensitivity line (task 5.5) need
more than that diff: they re-run `judge_one` directly, under different
flags, over the current `signature`+`normalized` rows — using the same
known-set context `judge.run()` builds (`judge.build_known_set_context`),
so this module never re-derives the known-set differently than the stage
that actually wrote `verdict`.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import baseline  # noqa: E402
import judge as judge_stage  # noqa: E402
import store  # noqa: E402

# The rules this change introduces (tasks 3.5/4.6) — the only ones the
# per-rule/disagreements/sensitivity sections report on. Pre-existing D13
# attestation rules are not this change's effect and are out of scope for
# the diff.
NEW_RULE_NAMES = frozenset(
    {"fully-known-sentence", "proper-noun", "derived-from-proper-noun", "numeral"}
)


def _current_candidates(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute("SELECT signature_key, fields_json, verdict, verdict_evidence_json FROM candidate").fetchall()
    return {row["signature_key"]: row for row in rows}


def _decisions(conn: sqlite3.Connection) -> dict[str, str]:
    return {row["signature_key"]: row["decision"] for row in conn.execute("SELECT signature_key, decision FROM decision")}


def _candidate_entry(signature_key: str, row: sqlite3.Row) -> dict:
    fields = json.loads(row["fields_json"])
    evidence = json.loads(row["verdict_evidence_json"])
    return {
        "signature_key": signature_key,
        "text": fields.get("text"),
        "translations": [t.get("text") for t in fields.get("translations", [])],
        "note_type": fields.get("note_type"),
        "rule": evidence.get("rule"),
        "evidence": {k: v for k, v in evidence.items() if k != "rule"},
    }


def build_totals_and_per_rule(conn: sqlite3.Connection, baseline_snapshot: dict) -> tuple[dict, dict]:
    """Tasks 5.1-5.3: totals before/after, and every newly-skipped
    candidate grouped by the rule that skipped it."""
    before_eligible = set(baseline_snapshot["signature_keys"])
    candidates = _current_candidates(conn)
    after_eligible = {sig for sig, row in candidates.items() if row["verdict"] == "import"}

    newly_skipped = before_eligible - after_eligible

    per_rule: dict[str, list[dict]] = defaultdict(list)
    for sig in sorted(newly_skipped):
        row = candidates.get(sig)
        if row is None:
            # The signature no longer exists under this key — a re-run of
            # `key` changed signatures for an unrelated reason, not this
            # change's effect. Not this audit's concern (task 1.2 exists
            # precisely so this is distinguishable).
            continue
        entry = _candidate_entry(sig, row)
        per_rule[entry["rule"] or "(unknown)"].append(entry)

    totals = {
        "before": len(before_eligible),
        "after": len(after_eligible),
        "delta": len(before_eligible) - len(after_eligible),
        "newly_skipped": len(newly_skipped),
    }
    per_rule_summary = {rule: {"count": len(entries), "candidates": entries} for rule, entries in per_rule.items()}
    return totals, per_rule_summary


def build_disagreements(conn: sqlite3.Connection) -> list[dict]:
    """Task 5.4/D4: every candidate where a *new* rule would skip it, but
    the operator already decided it — recomputed with `apply_new_rules`
    forced on, since `judge.run()` itself never lets this happen to the
    written verdict (task 6.1/6.2). Reported, never acted on."""
    decisions = _decisions(conn)
    if not decisions:
        return []

    context = judge_stage.build_known_set_context(conn)
    rows_by_signature: dict[str, sqlite3.Row] = {}
    for row in judge_stage.rows_for_judging(conn):
        rows_by_signature.setdefault(row["signature_key"], row)

    disagreements = []
    for signature_key, decision in decisions.items():
        row = rows_by_signature.get(signature_key)
        if row is None:
            continue
        signature = judge_stage.row_signature(row)
        verdict, rule, evidence = judge_stage.judge_one(
            row["text"],
            signature,
            context["denylist"],
            context["known_tokens"],
            context["known_tokens_strong"],
            context["known_ngrams"],
            context["known_by_head_lemma"],
            context["lemma_map"],
            note_type=row["note_type"],
            translations=json.loads(row["translations_json"]),
            audio_ref=row["audio_ref"],
            apply_new_rules=True,
        )
        if verdict == "skip" and rule in NEW_RULE_NAMES and decision == "accept":
            disagreements.append(
                {
                    "signature_key": signature_key,
                    "text": row["text"],
                    "decision": decision,
                    "would_skip_rule": rule,
                    "evidence": evidence,
                }
            )
    return disagreements


def build_sensitivity(conn: sqlite3.Connection) -> dict:
    """Task 5.5/D2: the same fully-known-sentence totals with the audio
    condition enabled, so the 571-vs-2 trade-off is visible as evidence
    rather than asserted in a design doc."""
    context = judge_stage.build_known_set_context(conn)
    rows = judge_stage.rows_for_judging(conn)

    def count_fully_known_sentence_skips(require_no_audio: bool) -> int:
        count = 0
        for row in rows:
            signature = judge_stage.row_signature(row)
            verdict, rule, _evidence = judge_stage.judge_one(
                row["text"],
                signature,
                context["denylist"],
                context["known_tokens"],
                context["known_tokens_strong"],
                context["known_ngrams"],
                context["known_by_head_lemma"],
                context["lemma_map"],
                note_type=row["note_type"],
                translations=json.loads(row["translations_json"]),
                audio_ref=row["audio_ref"],
                require_no_audio_for_sentence_rule=require_no_audio,
                apply_new_rules=True,
            )
            if verdict == "skip" and rule == "fully-known-sentence":
                count += 1
        return count

    without_audio_condition = count_fully_known_sentence_skips(require_no_audio=False)
    with_audio_condition = count_fully_known_sentence_skips(require_no_audio=True)
    return {
        "fully_known_sentence_default": without_audio_condition,
        "fully_known_sentence_no_audio_required": with_audio_condition,
    }


def build_report(conn: sqlite3.Connection, baseline_snapshot: dict) -> dict:
    totals, per_rule = build_totals_and_per_rule(conn, baseline_snapshot)
    return {
        "totals": totals,
        "per_rule": per_rule,
        "disagreements": build_disagreements(conn),
        "sensitivity": build_sensitivity(conn),
    }


def format_report(report: dict) -> str:
    lines = []
    totals = report["totals"]
    lines.append(
        f"eligible: {totals['before']} -> {totals['after']} "
        f"(-{totals['delta']}, {totals['newly_skipped']} newly skipped)"
    )
    lines.append("")
    for rule, summary in sorted(report["per_rule"].items(), key=lambda kv: -kv[1]["count"]):
        lines.append(f"## {rule} ({summary['count']})")
        for entry in summary["candidates"]:
            gloss = ", ".join(entry["translations"]) if entry["translations"] else "(no gloss)"
            lines.append(f"  {entry['text']!r} [{entry['note_type']}] -> {gloss}")
        lines.append("")

    disagreements = report["disagreements"]
    lines.append(f"## disagreements ({len(disagreements)})")
    for entry in disagreements:
        lines.append(f"  {entry['text']!r} accepted, but {entry['would_skip_rule']} would now skip it")
    lines.append("")

    sensitivity = report["sensitivity"]
    lines.append("## sensitivity (fully-known-sentence, audio condition)")
    lines.append(f"  default (no audio condition): {sensitivity['fully_known_sentence_default']}")
    lines.append(f"  audio required absent:        {sensitivity['fully_known_sentence_no_audio_required']}")
    return "\n".join(lines)


def recover(conn: sqlite3.Connection, signature_key: str) -> bool:
    """Task 5.6: return a newly-skipped candidate to the queue without
    re-running earlier stages and without discarding decisions — a direct
    `verdict` flip on the existing `candidate` row. `decision` (if any) is
    untouched, so an operator who separately decided this candidate keeps
    that decision."""
    cur = conn.execute("UPDATE candidate SET verdict = 'import' WHERE signature_key = ?", (signature_key,))
    conn.commit()
    return cur.rowcount > 0


def run_with_conn(conn: sqlite3.Connection, *, recover_signature_key: str | None = None, as_json: bool = False) -> int:
    """Shared by this module's own CLI and `cli.py audit` (task 5.1), so
    both open exactly one connection rather than `cli.py` opening one and
    this module opening a second against the same file."""
    if recover_signature_key:
        recovered = recover(conn, recover_signature_key)
        print(f"audit: recovered {recover_signature_key}" if recovered else f"audit: no such signature_key {recover_signature_key!r}")
        return 0 if recovered else 1

    if not baseline.BASELINE_PATH.exists():
        print(
            f"audit: no baseline at {baseline.BASELINE_PATH} — run `cli.py baseline` before any rule changed",
            file=sys.stderr,
        )
        return 1
    baseline_snapshot = json.loads(baseline.BASELINE_PATH.read_text(encoding="utf-8"))

    report = build_report(conn, baseline_snapshot)
    print(json.dumps(report, ensure_ascii=False, indent=2) if as_json else format_report(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Review-eligibility audit (review-queue-filters section 5).")
    parser.add_argument("--db", default=str(store.DEFAULT_DB_PATH))
    parser.add_argument("--recover", metavar="SIGNATURE_KEY", help="return one newly-skipped candidate to the queue")
    parser.add_argument("--json", action="store_true", help="print the raw report as JSON instead of formatted text")
    args = parser.parse_args(argv)

    conn = store.connect(args.db)
    return run_with_conn(conn, recover_signature_key=args.recover, as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
