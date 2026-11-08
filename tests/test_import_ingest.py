"""Tests for scripts/import/ingest.py — section 2 of bulk-import-anki-csv.

These run against the real source archives in `import/` (gitignored,
~450MB) because the whole point of this stage is verbatim parsing of those
specific files — there is no meaningful fixture substitute for "did we read
the real .apkg correctly". Skipped automatically wherever `import/` doesn't
have the source files (e.g. a fresh clone without the operator's data).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import ingest as import_ingest  # noqa: E402
import store as import_store  # noqa: E402

pytestmark = pytest.mark.skipif(
    not all((import_ingest.IMPORT_DIR / spec["file"]).exists() for spec in import_ingest.APKG_SOURCES.values()),
    reason="import/ source archives are gitignored and not present in this checkout",
)


@pytest.fixture
def conn(tmp_path):
    connection = import_store.connect(tmp_path / "candidates.db")
    yield connection
    connection.close()


def test_apkg_sources_are_plain_sqlite_not_assumed():
    for source in import_ingest.APKG_SOURCES:
        path = import_ingest.IMPORT_DIR / import_ingest.APKG_SOURCES[source]["file"]
        import zipfile

        with zipfile.ZipFile(path) as archive:
            header = archive.read("collection.anki21")[:16]
        assert header.startswith(b"SQLite format 3"), source


@pytest.mark.parametrize("source", list(import_ingest.APKG_SOURCES))
def test_apkg_source_matches_expected_count_after_model_filtering(source):
    rows, _total = import_ingest.ingest_apkg_source(source)
    assert len(rows) == import_ingest.APKG_SOURCES[source]["expected_count"]


def test_core6k_excludes_grammar_model():
    rows, total = import_ingest.ingest_apkg_source("core6k")
    assert total == 6608  # 6,192 Core + 191 Country + 225 Grammar
    assert all(row["note_type"] != "Grammar" for row in rows)


def test_freq6k_excludes_read_me_model():
    rows, total = import_ingest.ingest_apkg_source("freq6k")
    assert total == 3882  # 3,881 data notes + 1 Read me
    assert all(row["note_type"] != "6000 Most Frequent Norwegian Words: Read me" for row in rows)


def test_ntnu_malformed_inflection_is_preserved_verbatim_not_corrected():
    rows, _ = import_ingest.ingest_apkg_source("ntnu")
    arkitektur = next(r for r in rows if r["fields"]["Word"].strip() == "arkitektur")
    assert arkitektur["fields"]["Inflection"].strip() == "arkitekturen, arkitekturerarkitekturene"


def test_apkg_media_refs_resolve_to_archive_member_keys():
    rows, _ = import_ingest.ingest_apkg_source("ntnu")
    with_audio = next(r for r in rows if r["media"])
    (filename, member) = next(iter(with_audio["media"].items()))
    assert filename.endswith(".mp3")
    assert member is not None and member.isdigit()


def test_resolve_note_due_returns_min_when_cards_agree():
    assert import_ingest.resolve_note_due(1, [42, 42]) == 42


def test_resolve_note_due_raises_when_cards_disagree():
    with pytest.raises(import_ingest.IngestCountMismatch):
        import_ingest.resolve_note_due(1, [42, 99])


def test_resolve_note_due_returns_none_for_no_cards():
    assert import_ingest.resolve_note_due(1, []) is None


def test_core6k_due_is_captured_as_a_genuine_frequency_rank():
    rows, _ = import_ingest.ingest_apkg_source("core6k")
    core_rows = [r for r in rows if r["note_type"] == "Norwegian Core"]
    dues = [r["due"] for r in core_rows]
    assert all(d is not None for d in dues)
    assert min(dues) == 1
    assert max(dues) == 6000
    assert len(set(dues)) == 6000


def test_non_core6k_sources_have_no_due():
    rows, _ = import_ingest.ingest_apkg_source("ntnu")
    assert all(r["due"] is None for r in rows)


def test_csv_row_count_matches_expected():
    rows = import_ingest.ingest_csv_source()
    assert len(rows) == import_ingest.CSV_EXPECTED_COUNT


def test_csv_non_numeric_kapittel_is_kept_as_string():
    rows = import_ingest.ingest_csv_source()
    assert any(row["fields"]["Kapittel"] == "11 Ord og begreper" for row in rows)


def test_csv_section_header_is_carried_down_to_following_rows():
    rows = import_ingest.ingest_csv_source()
    row = next(r for r in rows if r["fields"]["Original word"] == "okkupasjon /en")
    assert row["fields"]["Kapittel"] == "12 Ord og bergreper"


def test_full_ingest_run_matches_measured_counts_and_populates_raw_note(conn):
    run_id = import_store.start_run(conn, "ingest")
    count_in, count_out, count_discarded = import_ingest.run(conn, run_id)

    assert count_in == 15488
    assert count_out == 15262
    assert count_discarded == 226

    per_source = dict(conn.execute("SELECT source, COUNT(*) FROM raw_note GROUP BY source").fetchall())
    assert per_source == {
        "ntnu": 749,
        "a1_31k": 3097,
        "core6k": 6383,
        "freq6k": 3881,
        "herpaberget": 1152,
    }


def test_rerunning_ingest_replaces_raw_note_without_duplicating(conn):
    run_id_1 = import_store.start_run(conn, "ingest")
    import_ingest.run(conn, run_id_1)
    first_count = conn.execute("SELECT COUNT(*) FROM raw_note").fetchone()[0]

    run_id_2 = import_store.start_run(conn, "ingest")
    import_ingest.run(conn, run_id_2)
    second_count = conn.execute("SELECT COUNT(*) FROM raw_note").fetchone()[0]

    assert first_count == second_count == 15262
    # every row now belongs to the second run, not a duplicate of the first
    assert conn.execute("SELECT COUNT(*) FROM raw_note WHERE run_id = ?", (run_id_1,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM raw_note WHERE run_id = ?", (run_id_2,)).fetchone()[0] == 15262


def test_full_ingest_run_populates_due_only_for_core6k(conn):
    run_id = import_store.start_run(conn, "ingest")
    import_ingest.run(conn, run_id)

    non_core6k_with_due = conn.execute(
        "SELECT COUNT(*) FROM raw_note WHERE source != 'core6k' AND due IS NOT NULL"
    ).fetchone()[0]
    assert non_core6k_with_due == 0

    core6k_with_due = conn.execute(
        "SELECT COUNT(*) FROM raw_note WHERE source = 'core6k' AND due IS NOT NULL"
    ).fetchone()[0]
    assert core6k_with_due == 6383


def test_fields_json_round_trips_through_sqlite(conn):
    run_id = import_store.start_run(conn, "ingest")
    import_ingest.run(conn, run_id)
    row = conn.execute("SELECT fields_json FROM raw_note WHERE source = 'herpaberget' LIMIT 1").fetchone()
    fields = json.loads(row["fields_json"])
    assert set(fields) == set(import_ingest.CSV_FIELDS)
