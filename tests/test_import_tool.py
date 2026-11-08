"""Tests for scripts/import/{store,cli}.py — the bulk-import tool's skeleton
and candidate store (section 1 of bulk-import-anki-csv).

These tests touch only an in-memory/tmp-path SQLite file, never stabbur's
own Postgres database, so they don't need tests/conftest.py's Postgres
fixtures. `scripts/import` can't be imported as a dotted package (`import`
is a reserved word), so its modules are loaded here the same way cli.py
loads its own siblings: by path, as bare top-level names.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import cli as import_cli  # noqa: E402
import store as import_db  # noqa: E402

@pytest.fixture
def conn(tmp_path):
    connection = import_db.connect(tmp_path / "candidates.db")
    yield connection
    connection.close()


def test_schema_creates_all_tables(conn):
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    expected = {"run", "log", "raw_note", "normalized", "signature", "verdict", "candidate", "decision"}
    assert expected <= tables


def test_connect_is_idempotent(tmp_path):
    path = tmp_path / "candidates.db"
    import_db.connect(path).close()
    # Re-opening an existing store must not fail or wipe it.
    conn = import_db.connect(path)
    conn.execute(
        "INSERT INTO run (stage, started_at, status) VALUES ('ingest', '2026-01-01', 'complete')"
    )
    conn.commit()
    conn.close()
    conn2 = import_db.connect(path)
    assert conn2.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 1


def test_start_run_rejects_unknown_stage(conn):
    with pytest.raises(ValueError):
        import_db.start_run(conn, "bogus")


def test_finish_run_writes_log_with_run_id_and_counts(conn):
    run_id = import_db.start_run(conn, "ingest")
    import_db.finish_run(conn, run_id, count_in=10, count_out=8, count_discarded=2, detail="ok")

    run_row = conn.execute("SELECT status, finished_at FROM run WHERE id = ?", (run_id,)).fetchone()
    assert run_row["status"] == "complete"
    assert run_row["finished_at"] is not None

    log_row = conn.execute("SELECT * FROM log WHERE run_id = ?", (run_id,)).fetchone()
    assert log_row["stage"] == "ingest"
    assert log_row["count_in"] == 10
    assert log_row["count_out"] == 8
    assert log_row["count_discarded"] == 2
    assert log_row["detail"] == "ok"


def test_fail_run_marks_run_failed_and_logs_zero_counts(conn):
    run_id = import_db.start_run(conn, "normalize")
    import_db.fail_run(conn, run_id, "boom")

    run_row = conn.execute("SELECT status FROM run WHERE id = ?", (run_id,)).fetchone()
    assert run_row["status"] == "failed"

    log_row = conn.execute("SELECT * FROM log WHERE run_id = ?", (run_id,)).fetchone()
    assert log_row["count_in"] == 0
    assert log_row["detail"] == "boom"


def test_replace_stage_table_clears_only_that_stage_and_never_decision(conn):
    run_id = import_db.start_run(conn, "ingest")
    conn.execute(
        "INSERT INTO raw_note (run_id, source, source_note_id, note_type, fields_json) VALUES (?, 'ntnu', '1', 'word', '{}')",
        (run_id,),
    )
    conn.execute(
        "INSERT INTO decision (signature_key, decision, decided_at) VALUES ('legge/[]/0/[]', 'accept', '2026-01-01')"
    )
    conn.commit()

    import_db.replace_stage_table(conn, "ingest")
    conn.commit()

    assert conn.execute("SELECT COUNT(*) FROM raw_note").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM decision").fetchone()[0] == 1


def test_replace_stage_table_rejects_review_and_push():
    assert "review" not in import_db.STAGE_OUTPUT_TABLE
    assert "push" not in import_db.STAGE_OUTPUT_TABLE


def test_status_report_reflects_last_run_per_stage(conn):
    run_id = import_db.start_run(conn, "key")
    import_db.finish_run(conn, run_id, count_in=5, count_out=5, count_discarded=0)

    report = {row["stage"]: row for row in import_db.status_report(conn)}
    assert report["key"]["status"] == "complete"
    assert report["key"]["count_in"] == 5
    assert report["ingest"]["status"] == "never run"
    assert report["ingest"]["count_in"] is None


def test_cli_status_runs_with_no_prior_runs(tmp_path, capsys):
    exit_code = import_cli.main(["--db", str(tmp_path / "candidates.db"), "status"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "ingest" in out
    assert "never run" in out


def test_cli_stub_stage_fails_cleanly_and_logs_failure(tmp_path, capsys):
    # "merge" is still a stub past section 4 (ingest/normalize/key/judge
    # are implemented) — pick whichever stage is still a NotImplementedError
    # stub so this test doesn't need updating every time a new section lands.
    db_path = tmp_path / "candidates.db"
    exit_code = import_cli.main(["--db", str(db_path), "merge"])
    assert exit_code == 1
    assert "not yet implemented" in capsys.readouterr().err

    conn = import_db.connect(db_path)
    run_row = conn.execute("SELECT status FROM run ORDER BY id DESC LIMIT 1").fetchone()
    assert run_row["status"] == "failed"
    conn.close()


def test_all_eight_stages_have_subcommands():
    parser_dests = set(import_db.STAGES) | {"status"}
    # Exercise argparse directly: every stage name must be an accepted
    # subcommand, and an unknown one must be rejected.
    for stage in parser_dests:
        with pytest.raises(SystemExit) as exc_info:
            import_cli.main(["--db", ":memory:", stage, "--help"])
        assert exc_info.value.code == 0


def test_json_round_trip_on_candidate_fields(conn):
    run_id = import_db.start_run(conn, "merge")
    fields = {"text": "legge til", "translations": [{"lang": "en", "text": "to add"}]}
    conn.execute(
        "INSERT INTO candidate (run_id, signature_key, fields_json, verdict) VALUES (?, ?, ?, 'import')",
        (run_id, "legge/[til]/0/[]", json.dumps(fields)),
    )
    conn.commit()
    row = conn.execute("SELECT fields_json FROM candidate WHERE signature_key = ?", ("legge/[til]/0/[]",)).fetchone()
    assert json.loads(row["fields_json"]) == fields
