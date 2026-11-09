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
# Human-audio-only selection at merge (task 1.6, design D7)
# ---------------------------------------------------------------------------


def test_candidate_with_only_synthesised_audio_records_none():
    rows = [_row("core6k", audio_ref="hypertts-123.mp3"), _row("freq6k", audio_ref="ordpar-456.mp3")]
    fields, sources, conflicts, _order_key = import_merge.merge_group(rows)
    assert "audio_ref" not in fields
    assert "audio_ref" not in sources
    assert "audio_ref" not in conflicts


def test_candidate_with_human_audio_keeps_it_even_if_lower_priority_source_has_synthesised():
    rows = [
        _row("core6k", audio_ref="hypertts-123.mp3"),
        _row("a1_31k", audio_ref="a1-recording.mp3"),
    ]
    fields, sources, _conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["audio_ref"] == "a1-recording.mp3"
    assert sources["audio_ref"] == "a1_31k"


def test_ntnu_human_audio_outranks_a1_human_audio():
    rows = [_row("a1_31k", audio_ref="a1-recording.mp3"), _row("ntnu", audio_ref="ntnu-recording.mp3")]
    fields, sources, conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["audio_ref"] == "ntnu-recording.mp3"
    assert sources["audio_ref"] == "ntnu"
    assert conflicts["audio_ref"] == [{"source": "a1_31k", "value": "a1-recording.mp3"}]


# ---------------------------------------------------------------------------
# Part-of-speech inference + lemma (import-pos-lemma-inference, tasks
# 2.1-2.7, 3.1-3.2, 4.1-4.4, 5.1-5.6)
# ---------------------------------------------------------------------------


def test_inflection_shape_outranks_source_label_and_records_conflict():
    """Task 5.2: a candidate whose inflection shape says noun and whose
    source label says adjective resolves to substantiv and records the
    disagreement as a conflict (design D4)."""
    rows = [_row("ntnu", inflections={"article": "en", "sg_indef": "katt", "sg_def": "katten"})]
    rows.append(_row("freq6k", pos="adjektiv"))
    fields, sources, conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["pos"] == "substantiv"
    assert conflicts["pos"] == [{"source": "signal:source_word_class", "value": "adjektiv"}]


def test_text_prefix_signal_resolves_pos_when_no_inflections():
    rows = [_row("csv_placeholder", text="å gå")]
    rows[0]["source"] = "herpaberget"
    fields, _sources, _conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["pos"] == "verb"


def test_source_word_class_signal_resolves_pos_in_isolation():
    rows = [_row("freq6k", text="katt", pos="substantiv")]
    fields, _sources, _conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["pos"] == "substantiv"


def test_translation_prefix_is_the_only_resolving_signal():
    rows = [_row("freq6k", text="katt", translations=[{"lang": "en", "text": "a cat"}])]
    fields, sources, _conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["pos"] == "substantiv"
    assert sources["pos"] == "signal:translation_prefix"


def test_expression_notes_get_neither_pos_nor_lemma():
    rows = [
        _row(
            "csv_placeholder",
            note_type="expression",
            text="bli kvitt",
            pos="verb",
            translations=[{"lang": "en", "text": "to get rid of"}],
        )
    ]
    rows[0]["source"] = "herpaberget"
    fields, sources, conflicts, _order_key = import_merge.merge_group(rows)
    assert "pos" not in fields
    assert "pos" not in sources
    assert "pos" not in conflicts
    assert "lemma" not in fields


def test_listening_notes_get_neither_pos_nor_lemma():
    rows = [_row("a1_31k", note_type="listening", text="noen ganger")]
    fields, _sources, _conflicts, _order_key = import_merge.merge_group(rows)
    assert "pos" not in fields
    assert "lemma" not in fields


def test_unresolvable_word_candidate_leaves_pos_unset_not_defaulted():
    rows = [_row("ntnu", text="møte")]
    fields, sources, conflicts, _order_key = import_merge.merge_group(rows)
    assert "pos" not in fields
    assert "pos" not in sources
    assert "pos" not in conflicts


def test_lemma_strips_leading_article_for_word_notes():
    rows = [_row("ntnu", text="en katt")]
    fields, _sources, _conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["lemma"] == "katt"


def test_lemma_strips_leading_infinitive_marker_for_word_notes():
    rows = [_row("ntnu", text="å spise")]
    fields, _sources, _conflicts, _order_key = import_merge.merge_group(rows)
    assert fields["lemma"] == "spise"


# ---------------------------------------------------------------------------
# core6k rank as its own ordering tier (task 1.3, design D6)
# ---------------------------------------------------------------------------


def test_merge_group_carries_core6k_rank_as_its_own_order_signal():
    rows = [_row("core6k", order_signal={"core6k_rank": 42})]
    _fields, _sources, _conflicts, order_key = import_merge.merge_group(rows)
    assert order_key["core6k_rank"] == 42
    assert order_key["frequency_index"] is None


def test_core6k_rank_does_not_merge_with_freq6k_frequency_index():
    rows = [_row("freq6k", order_signal={"frequency_index": 10}), _row("core6k", order_signal={"core6k_rank": 5})]
    _fields, _sources, _conflicts, order_key = import_merge.merge_group(rows)
    assert order_key == {"frequency_index": 10, "core6k_rank": 5, "cefr": None, "chapter": None}


def test_candidate_with_only_core6k_rank_sorts_before_candidate_with_no_signal():
    only_core6k = import_merge.order_sort_key({"frequency_index": None, "core6k_rank": 100, "cefr": None, "chapter": None})
    no_signal = import_merge.order_sort_key({"frequency_index": None, "core6k_rank": None, "cefr": None, "chapter": None})
    assert only_core6k < no_signal


def test_freq6k_frequency_index_still_outranks_core6k_rank():
    freq6k_signal = import_merge.order_sort_key(
        {"frequency_index": 500, "core6k_rank": None, "cefr": None, "chapter": None}
    )
    core6k_signal = import_merge.order_sort_key({"frequency_index": None, "core6k_rank": 1, "cefr": None, "chapter": None})
    assert freq6k_signal < core6k_signal


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


def test_ordering_coverage_rises_to_roughly_74_percent_with_core6k_rank(merged_conn):
    """Task 1.3: from 2,877/7,022 (41%) to ~5,170 (74%) once core6k's rank
    is a usable signal alongside freq6k's."""
    import json

    rows = merged_conn.execute(
        "SELECT order_key_json FROM candidate WHERE verdict = 'import'"
    ).fetchall()
    total = len(rows)
    ordered = sum(
        1
        for row in rows
        if (lambda k: k["frequency_index"] is not None or k["core6k_rank"] is not None or k["cefr"] or k["chapter"])(
            json.loads(row["order_key_json"])
        )
    )
    assert total == 7022
    assert 0.70 <= ordered / total <= 0.78


def test_human_audio_coverage_drops_to_roughly_2100_items(merged_conn):
    """Task 1.6: of the 6,269 queue items design.md measured carrying any
    audio_ref before this fix, only the ~2,102 with genuine human
    recordings should keep one afterwards."""
    import json

    rows = merged_conn.execute(
        "SELECT fields_json FROM candidate WHERE verdict = 'import'"
    ).fetchall()
    with_audio = sum(1 for row in rows if json.loads(row["fields_json"]).get("audio_ref"))
    assert 2000 <= with_audio <= 2200


def test_pos_lemma_corpus_distribution_matches_measured(merged_conn):
    """Task 5.7: real post-run distribution (recorded in design.md per task
    6.4), measured directly against this bundle rather than assumed from
    the original design estimate — same convention this change's other
    stages already follow for measured-not-assumed figures."""
    import json
    from collections import Counter

    rows = merged_conn.execute(
        "SELECT fields_json, conflicts_json FROM candidate WHERE verdict = 'import'"
    ).fetchall()

    pos_counts: Counter = Counter()
    word_count = 0
    unresolved = 0
    lemma_count = 0
    conflict_count = 0
    off_vocabulary = set()
    for row in rows:
        fields = json.loads(row["fields_json"])
        if fields.get("note_type") != "word":
            assert "pos" not in fields
            assert "lemma" not in fields
            continue
        word_count += 1
        pos = fields.get("pos")
        if pos is None:
            unresolved += 1
        else:
            pos_counts[pos] += 1
            if pos not in import_normalize.CANONICAL_POS:
                off_vocabulary.add(pos)
        if fields.get("lemma"):
            lemma_count += 1
        if "pos" in json.loads(row["conflicts_json"]):
            conflict_count += 1

    assert word_count == 7273
    assert lemma_count == word_count  # every word note gets a lemma (task 4.1)
    assert not off_vocabulary
    assert 3400 <= pos_counts["substantiv"] <= 3550
    assert 1100 <= pos_counts["verb"] <= 1200
    assert 650 <= pos_counts["adjektiv"] <= 750
    assert 1600 <= unresolved <= 1800
    assert 20 <= conflict_count <= 60  # design.md's ~38, signal disagreement is rare by construction


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
