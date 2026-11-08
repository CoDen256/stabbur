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
    raise NotImplementedError("ingest lands in section 2 (tasks 2.1-2.5)")


def normalize(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 3: field mapping + notation parsing, `raw_note` -> `normalized`."""
    raise NotImplementedError("normalize lands in section 3 (tasks 3.1-3.9)")


def key(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 4.4: lexeme signature builder, `normalized` -> `signature`."""
    raise NotImplementedError("key lands in section 4 (task 4.4)")


def judge(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 4: known-set match against stock, `signature` -> `verdict`."""
    raise NotImplementedError("judge lands in section 4 (tasks 4.1-4.3, 4.5-4.8)")


def merge(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 5: one candidate per signature, by source priority."""
    raise NotImplementedError("merge lands in section 5 (tasks 5.1-5.5)")


def review(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 6: interactive accept/reject/edit, writing only to `decision`."""
    raise NotImplementedError("review lands in section 6 (tasks 6.1-6.4)")


def push(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    """Section 7: accepted candidates -> `POST /api/notes` + blob upload."""
    raise NotImplementedError("push lands in section 7 (tasks 7.1-7.4)")


STAGE_FUNCS = {
    "ingest": ingest,
    "normalize": normalize,
    "key": key,
    "judge": judge,
    "merge": merge,
    "review": review,
    "push": push,
}
