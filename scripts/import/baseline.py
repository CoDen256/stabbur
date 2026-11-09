"""
scripts/import/baseline.py — review-eligibility snapshot (review-queue-
filters, tasks 1.1/1.2).

Captures the state the whole change is judged against, *before* any new
skip rule touches `judge.py`: every `signature_key` currently eligible for
review (`candidate.verdict = 'import'`), broken down by note type, plus the
`verdict` table's rule histogram — so a later audit (section 5) can tell
this change's effect apart from a rule that shifted for an unrelated reason
(task 1.2).

Written to `import/baseline_eligibility.json`, alongside `candidates.db`
itself: reproducible from the pipeline, never committed (see
`.gitignore`'s `/import`).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

# Same reason as cli.py: `scripts/import` can't be a dotted package, so
# `store` is only importable once this directory is on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import store  # noqa: E402

BASELINE_PATH = Path(__file__).resolve().parent.parent.parent / "import" / "baseline_eligibility.json"


def capture(conn: sqlite3.Connection) -> dict:
    per_type = Counter()
    signature_keys = []
    for row in conn.execute("SELECT signature_key, fields_json FROM candidate WHERE verdict = 'import'"):
        per_type[json.loads(row["fields_json"])["note_type"]] += 1
        signature_keys.append(row["signature_key"])
    signature_keys.sort()

    rule_histogram = {
        f"{rule or '(none)'}:{verdict}": count
        for rule, verdict, count in conn.execute(
            "SELECT rule, verdict, COUNT(*) FROM verdict GROUP BY rule, verdict"
        )
    }

    return {
        "total_import": len(signature_keys),
        "per_type": dict(per_type),
        "signature_keys": signature_keys,
        "verdict_rule_histogram": rule_histogram,
    }


def write(conn: sqlite3.Connection) -> dict:
    """Capture and persist the snapshot, printing a one-line summary.
    Shared by `cli.py baseline` and this module's own `main`."""
    snapshot = capture(conn)
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"baseline: {snapshot['total_import']} eligible {snapshot['per_type']}; "
        f"written to {BASELINE_PATH}"
    )
    return snapshot


def main(argv: list[str] | None = None) -> int:
    write(store.connect(str(store.DEFAULT_DB_PATH)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
