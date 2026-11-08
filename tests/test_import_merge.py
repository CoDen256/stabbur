"""Tests for scripts/import/merge.py — section 5 of bulk-import-anki-csv
(tasks 5.1-5.5): `normalized` grouped by lexeme signature -> `candidate`.

Unit tests for `merge_group`/`order_sort_key` run without the real
archives. The full-pipeline tests need them (to exercise `run()` against
real `normalized`/`signature` data), same skip convention as the other
import-tool test modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import ingest as import_ingest  # noqa: E402
import key as import_key  # noqa: E402
import merge as import_merge  # noqa: E402
import normalize as import_normalize  # noqa: E402
import store as import_store  # noqa: E402

_HAS_SOURCES = all((import_ingest.IMPORT_DIR / spec["file"]).exists() for spec in import_ingest.APKG_SOURCES.values())


def _row(source, **overrides):
    base = {
        "source": source,
        "note_type": "word",
        "text": None,
        "pos": None,
        "translations": [],
        "context_text": None,
        "transcription": None,
        "inflections": {},
        "audio_ref": None,
        "order_signal": {},
        "tags": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# merge_group (tasks 5.2, 5.3) — pure unit tests, no archives needed
# ---------------------------------------------------------------------------


def test_highest_priority_non_empty_value_wins():
    rows = [
        _row("csv_placeholder", text="gammel-tekst"),
        _row("ntnu", text="ny"),
        _row("freq6k", text="eldre"),
    ]
    # fix the placeholder source name to a real low-priority one
    rows[0]["source"] = "herpaberget"
    fields, sources, conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["text"] == "ny"
    assert sources["text"] == "ntnu"


def test_lower_priority_source_used_when_higher_priority_field_empty():
    rows = [_row("ntnu", text=None), _row("a1_31k", text="front-text")]
    fields, sources, _conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["text"] == "front-text"
    assert sources["text"] == "a1_31k"


def test_conflicting_values_retained_not_discarded():
    rows = [
        _row("ntnu", translations=[{"lang": "en", "text": "to plan"}]),
        _row("core6k", translations=[{"lang": "en", "text": "to schedule"}]),
    ]
    fields, _sources, conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["translations"] == [{"lang": "en", "text": "to plan"}]
    assert conflicts["translations"] == [{"source": "core6k", "value": [{"lang": "en", "text": "to schedule"}]}]


def test_no_conflict_recorded_when_only_one_source_has_a_value():
    rows = [_row("ntnu", pos="verb"), _row("csv_placeholder", pos=None)]
    rows[1]["source"] = "herpaberget"
    _fields, _sources, conflicts, _order_key = import_merge.merge_group(rows)
    assert "pos" not in conflicts


def test_fields_are_not_averaged_concatenated_or_voted():
    """Design D8: the highest-priority non-empty value wins outright — no
    merging of list fields like translations across sources."""
    rows = [
        _row("ntnu", translations=[{"lang": "en", "text": "a"}]),
        _row("a1_31k", translations=[{"lang": "en", "text": "b"}]),
        _row("core6k", translations=[{"lang": "en", "text": "c"}]),
    ]
    fields, _sources, conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["translations"] == [{"lang": "en", "text": "a"}]
    assert len(conflicts["translations"]) == 2


# ---------------------------------------------------------------------------
# order_sort_key (task 5.5, design D7)
# ---------------------------------------------------------------------------


def test_frequency_index_sorts_before_cefr_and_chapter():
    a = import_merge.order_sort_key({"frequency_index": 5, "cefr": None, "chapter": None})
    b = import_merge.order_sort_key({"frequency_index": 10, "cefr": "CEFR::A1", "chapter": None})
    assert a < b


def test_candidate_with_no_signal_sorts_last():
    with_signal = import_merge.order_sort_key({"frequency_index": 9999, "cefr": None, "chapter": None})
    no_signal = import_merge.order_sort_key({"frequency_index": None, "cefr": None, "chapter": None})
    assert with_signal < no_signal


def test_chapter_breaks_ties_when_no_frequency_or_cefr():
    early = import_merge.order_sort_key({"frequency_index": None, "cefr": None, "chapter": "1"})
    late = import_merge.order_sort_key({"frequency_index": None, "cefr": None, "chapter": "9"})
    assert early < late


# ---------------------------------------------------------------------------
# Full pipeline (tasks 5.1, 5.4) — needs the real archives + stock bundle
# ---------------------------------------------------------------------------

import stock as import_stock  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (_HAS_SOURCES and import_stock.stock_bundle_path().exists()),
    reason="needs both import/ source archives and the stock bundle (STABBUR_IMPORT_STOCK_BUNDLE), neither tracked in git",
)


@pytest.fixture(scope="module")
def merged_conn(tmp_path_factory):
    import judge as import_judge

    tmp_path = tmp_path_factory.mktemp("import_db")
    conn = import_store.connect(tmp_path / "candidates.db")
    run_id = import_store.start_run(conn, "ingest")
    import_ingest.run(conn, run_id)
    run_id = import_store.start_run(conn, "normalize")
    import_normalize.run(conn, run_id)
    run_id = import_store.start_run(conn, "key")
    import_key.run(conn, run_id)
    run_id = import_store.start_run(conn, "judge")
    import_judge.run(conn, run_id)
    run_id = import_store.start_run(conn, "merge")
    import_merge.run(conn, run_id)
    yield conn
    conn.close()


def test_one_candidate_per_signature(merged_conn):
    distinct_signatures = merged_conn.execute("SELECT COUNT(DISTINCT signature_key) FROM signature").fetchone()[0]
    candidate_count = merged_conn.execute("SELECT COUNT(*) FROM candidate").fetchone()[0]
    assert candidate_count == distinct_signatures


def test_cross_source_overlap_shows_merging_not_duplication(merged_conn):
    """Task 5.4: a meaningful number of signatures must be attested by
    more than one source — if merge were silently producing duplicates
    instead of merging, every signature would show exactly one
    contributing source."""
    rows = merged_conn.execute(
        """
        SELECT s.signature_key, n.source
        FROM normalized n JOIN signature s ON s.normalized_id = n.id
        """
    ).fetchall()
    from collections import defaultdict

    groups = defaultdict(set)
    for row in rows:
        groups[row["signature_key"]].add(row["source"])

    multi_source = sum(1 for sources in groups.values() if len(sources) > 1)
    assert multi_source > 1000  # design.md measured 2,510+733+423; this bundle measures ~3,897 — see design.md


def test_merge_is_idempotent_and_does_not_touch_decision(merged_conn):
    before = merged_conn.execute("SELECT COUNT(*) FROM decision").fetchone()[0]
    run_id = import_store.start_run(merged_conn, "merge")
    import_merge.run(merged_conn, run_id)
    after = merged_conn.execute("SELECT COUNT(*) FROM decision").fetchone()[0]
    assert before == after == 0
    # re-running replaced candidate, not duplicated it
    candidate_count = merged_conn.execute("SELECT COUNT(*) FROM candidate").fetchone()[0]
    distinct_signatures = merged_conn.execute("SELECT COUNT(DISTINCT signature_key) FROM signature").fetchone()[0]
    assert candidate_count == distinct_signatures
