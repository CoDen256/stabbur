"""
scripts/import/store.py — the SQLite candidate store (design D1, D2).

Named `store`, not `db`: `scripts/import` can't be a dotted package
(`import` is a reserved word) so its modules are always loaded as bare
top-level names (see cli.py) — `db` would collide with stabbur's own
top-level `db/` package already in `sys.modules`.

Eight tables: `run` + `log` (pipeline bookkeeping) and one output table per
pipeline stage (`raw_note`, `normalized`, `signature`, `verdict`, `candidate`)
plus `decision`, which is the one table no stage but `review` may write to
(tasks 1.2, 1.3).

Every stage-output table is fully replaced on re-run (task 1.5): a stage
calls `replace_stage_table` immediately before writing its fresh rows, so
re-running `normalize` discards the previous `normalized` rows but never
touches `signature`, `verdict`, `candidate`, or `decision`. `decision` is
never passed to `replace_stage_table` — enforced by it not being a key in
`STAGE_OUTPUT_TABLE` below.
"""

from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "import" / "candidates.db"

STAGES = ("ingest", "normalize", "key", "judge", "merge", "review", "push")

# Stage -> the single table it fully replaces on each run. `review` and
# `push` are deliberately absent: review writes only to `decision` (append/
# upsert, never a wholesale replace) and push updates `candidate.note_id` in
# place rather than regenerating the table.
STAGE_OUTPUT_TABLE = {
    "ingest": "raw_note",
    "normalize": "normalized",
    "key": "signature",
    "judge": "verdict",
    "merge": "candidate",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES run(id),
    stage TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    count_in INTEGER NOT NULL,
    count_out INTEGER NOT NULL,
    count_discarded INTEGER NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS raw_note (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES run(id),
    source TEXT NOT NULL,
    source_note_id TEXT NOT NULL,
    note_type TEXT NOT NULL,
    fields_json TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS normalized (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES run(id),
    raw_note_id INTEGER NOT NULL REFERENCES raw_note(id),
    source TEXT NOT NULL,
    note_type TEXT NOT NULL,
    text TEXT NOT NULL,
    pos TEXT,
    translations_json TEXT NOT NULL DEFAULT '[]',
    context_text TEXT,
    transcription TEXT,
    inflections_json TEXT NOT NULL DEFAULT '{}',
    audio_ref TEXT,
    order_signal_json TEXT NOT NULL DEFAULT '{}',
    notation_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS signature (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES run(id),
    normalized_id INTEGER NOT NULL REFERENCES normalized(id),
    signature_key TEXT NOT NULL,
    head_lemma TEXT NOT NULL,
    particles_json TEXT NOT NULL DEFAULT '[]',
    reflexive INTEGER NOT NULL DEFAULT 0,
    complements_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS verdict (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES run(id),
    signature_key TEXT NOT NULL,
    verdict TEXT NOT NULL,
    rule TEXT,
    evidence_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES run(id),
    signature_key TEXT NOT NULL UNIQUE,
    fields_json TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '{}',
    conflicts_json TEXT NOT NULL DEFAULT '{}',
    verdict TEXT NOT NULL,
    verdict_evidence_json TEXT NOT NULL DEFAULT '{}',
    order_key_json TEXT NOT NULL DEFAULT '{}',
    note_id TEXT
);

CREATE TABLE IF NOT EXISTS decision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signature_key TEXT NOT NULL UNIQUE,
    decision TEXT NOT NULL,
    edited_fields_json TEXT,
    decided_at TEXT NOT NULL
);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def start_run(conn: sqlite3.Connection, stage: str) -> int:
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}, expected one of {STAGES}")
    cur = conn.execute(
        "INSERT INTO run (stage, started_at, status) VALUES (?, ?, 'running')",
        (stage, _now()),
    )
    conn.commit()
    return cur.lastrowid


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    count_in: int,
    count_out: int,
    count_discarded: int,
    detail: str = "",
) -> None:
    run = conn.execute("SELECT stage, started_at FROM run WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise ValueError(f"no such run {run_id}")
    finished_at = _now()
    conn.execute(
        "UPDATE run SET finished_at = ?, status = 'complete' WHERE id = ?",
        (finished_at, run_id),
    )
    conn.execute(
        """
        INSERT INTO log (run_id, stage, started_at, finished_at, count_in, count_out, count_discarded, detail)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, run["stage"], run["started_at"], finished_at, count_in, count_out, count_discarded, detail),
    )
    conn.commit()


def fail_run(conn: sqlite3.Connection, run_id: int, detail: str) -> None:
    run = conn.execute("SELECT stage, started_at FROM run WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise ValueError(f"no such run {run_id}")
    finished_at = _now()
    conn.execute(
        "UPDATE run SET finished_at = ?, status = 'failed' WHERE id = ?",
        (finished_at, run_id),
    )
    conn.execute(
        """
        INSERT INTO log (run_id, stage, started_at, finished_at, count_in, count_out, count_discarded, detail)
        VALUES (?, ?, ?, ?, 0, 0, 0, ?)
        """,
        (run_id, run["stage"], run["started_at"], finished_at, detail),
    )
    conn.commit()


def replace_stage_table(conn: sqlite3.Connection, stage: str) -> None:
    """Delete all existing rows of `stage`'s output table. Never call this
    for `review` or `push` — there is no entry for them in
    STAGE_OUTPUT_TABLE, so passing them raises rather than silently
    no-op'ing."""
    table = STAGE_OUTPUT_TABLE[stage]
    conn.execute(f"DELETE FROM {table}")


def status_report(conn: sqlite3.Connection) -> list[dict]:
    """One row per stage: its most recent run (if any) and that run's
    logged counts, so an interrupted pipeline is legible at a glance."""
    report = []
    for stage in STAGES:
        last_run = conn.execute(
            "SELECT id, started_at, finished_at, status FROM run WHERE stage = ? ORDER BY id DESC LIMIT 1",
            (stage,),
        ).fetchone()
        last_log = conn.execute(
            """
            SELECT count_in, count_out, count_discarded, detail FROM log
            WHERE stage = ? ORDER BY id DESC LIMIT 1
            """,
            (stage,),
        ).fetchone()
        report.append(
            {
                "stage": stage,
                "run_id": last_run["id"] if last_run else None,
                "started_at": last_run["started_at"] if last_run else None,
                "finished_at": last_run["finished_at"] if last_run else None,
                "status": last_run["status"] if last_run else "never run",
                "count_in": last_log["count_in"] if last_log else None,
                "count_out": last_log["count_out"] if last_log else None,
                "count_discarded": last_log["count_discarded"] if last_log else None,
                "detail": last_log["detail"] if last_log else None,
            }
        )
    return report
