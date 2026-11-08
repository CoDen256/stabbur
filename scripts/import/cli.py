#!/usr/bin/env python3
"""
scripts/import/cli.py — entrypoint for the bulk-import tool (task 1.1).

Run as:
    python scripts/import/cli.py <ingest|normalize|key|judge|merge|review|push>
    python scripts/import/cli.py status

An offline, one-shot operator tool: not wired into `app.py`, nothing added
to `compose.yaml` — it talks to a running stabbur only via its existing
HTTP API, in the `push` stage (section 7).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# `scripts/import` can't be imported as a dotted package — `import` is a
# reserved word. So this file always runs as a script, and its sibling
# modules are loaded as bare top-level names (never `from . import store`)
# by putting this directory on sys.path first.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import store  # noqa: E402
from stages import STAGE_FUNCS  # noqa: E402


def run_stage(conn: sqlite3.Connection, stage: str) -> tuple[int, int, int]:
    run_id = store.start_run(conn, stage)
    try:
        count_in, count_out, count_discarded = STAGE_FUNCS[stage](conn, run_id)
    except Exception as exc:
        store.fail_run(conn, run_id, repr(exc))
        raise
    store.finish_run(conn, run_id, count_in=count_in, count_out=count_out, count_discarded=count_discarded)
    return count_in, count_out, count_discarded


def print_status(conn: sqlite3.Connection) -> None:
    rows = store.status_report(conn)
    print(f"{'stage':10} {'status':10} {'in':>6} {'out':>6} {'discarded':>10}  finished_at")
    for row in rows:
        def cell(key: str) -> str:
            value = row[key]
            return "-" if value is None else str(value)

        print(
            f"{row['stage']:10} {row['status']:10} "
            f"{cell('count_in'):>6} {cell('count_out'):>6} {cell('count_discarded'):>10}  "
            f"{row['finished_at'] or '-'}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="stabbur-import",
        description="Bulk vocabulary import pipeline (design.md D2).",
    )
    parser.add_argument("--db", default=str(store.DEFAULT_DB_PATH), help="path to the SQLite candidate store")
    sub = parser.add_subparsers(dest="command", required=True)
    for stage in store.STAGES:
        sub.add_parser(stage, help=f"run the {stage} stage")
    sub.add_parser("status", help="print per-stage run state")

    args = parser.parse_args(argv)
    conn = store.connect(args.db)

    if args.command == "status":
        print_status(conn)
        return 0

    try:
        count_in, count_out, count_discarded = run_stage(conn, args.command)
    except NotImplementedError as exc:
        print(f"{args.command}: not yet implemented — {exc}", file=sys.stderr)
        return 1
    print(f"{args.command}: in={count_in} out={count_out} discarded={count_discarded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
