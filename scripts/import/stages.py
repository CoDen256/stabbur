"""
scripts/import/stages.py — stub stage bodies, one per pipeline stage.

Each stub exists so the CLI skeleton (task 1.1) can wire up every
subcommand now, with the run/log lifecycle (task 1.4) and idempotent
replace-on-rerun behaviour (task 1.5) already exercised by
`cli.run_stage`. The actual parsing/matching/merge/push logic lands in
later sections (2-7) by filling in these functions — no change to
`cli.py` or `db.py` should be needed to do so.
"""

from __future__ import annotations

import sqlite3


def ingest(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 2: parse the four `.apkg` archives and seven CSV chapter
    exports verbatim into `raw_note`. Returns (count_in, count_out,
    count_discarded)."""
    import ingest as ingest_stage

    return ingest_stage.run(conn, run_id)


def normalize(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 3: field mapping + notation parsing, `raw_note` -> `normalized`."""
    import normalize as normalize_stage

    return normalize_stage.run(conn, run_id)


def key(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 4.4: lexeme signature builder, `normalized` -> `signature`."""
    import key as key_stage

    return key_stage.run(conn, run_id)


def judge(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 4: known-set match against stock, `signature` -> `verdict`."""
    import judge as judge_stage

    return judge_stage.run(conn, run_id)


def merge(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 5: one candidate per signature, by source priority."""
    import merge as merge_stage

    return merge_stage.run(conn, run_id)


def review(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 6: interactive accept/reject/edit, writing only to `decision`."""
    import review as review_stage

    return review_stage.run(conn, run_id)


def push(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 7: accepted candidates -> `POST /api/notes` + blob upload."""
    import push as push_stage

    return push_stage.run(conn, run_id)


STAGE_FUNCS = {
    "ingest": ingest,
    "normalize": normalize,
    "key": key,
    "judge": judge,
    "merge": merge,
    "review": review,
    "push": push,
}
