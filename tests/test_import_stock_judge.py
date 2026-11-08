"""Tests for scripts/import/{stock,key,judge}.py — section 4 of
bulk-import-anki-csv (known-set extraction, signature keying, judging).

Needs both the real import/ archives (section 2+3's prerequisite) and the
real stock bundle (`STABBUR_IMPORT_STOCK_BUNDLE`, or
`~/mjolnir/index.android.bundle.exploded/2113.js`) — skipped wherever
either is absent, same convention as test_import_ingest.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import ingest as import_ingest  # noqa: E402
import judge as import_judge  # noqa: E402
import key as import_key  # noqa: E402
import lexeme  # noqa: E402
import normalize as import_normalize  # noqa: E402
import stock as import_stock  # noqa: E402
import store as import_store  # noqa: E402

_HAS_SOURCES = all((import_ingest.IMPORT_DIR / spec["file"]).exists() for spec in import_ingest.APKG_SOURCES.values())
_HAS_STOCK = import_stock.stock_bundle_path().exists()

pytestmark = pytest.mark.skipif(
    not (_HAS_SOURCES and _HAS_STOCK),
    reason="needs both import/ source archives and the stock bundle (STABBUR_IMPORT_STOCK_BUNDLE), neither tracked in git",
)


@pytest.fixture(scope="module")
def stock_cards():
    return import_stock.load_stock_cards()


@pytest.fixture(scope="module")
def full_pipeline_conn(tmp_path_factory):
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
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# stock.py (tasks 4.1, 4.2)
# ---------------------------------------------------------------------------


def test_stock_excludes_c2x_decks(stock_cards):
    assert all(not c["DECK_ID"].startswith("C2") for c in stock_cards)
    assert len(stock_cards) == 2790  # 2,801 raw - 11 C2x (design.md correction: not 13/2,788)


def test_stock_extraction_is_content_driven_not_a_field_driven(stock_cards):
    """Regression: the first implementation keyed extraction off the
    card's `A` field, assuming it denoted which field holds Norwegian.
    It doesn't — found when the operator spot-checked `normalized` and
    noticed common known words (trene, viktig, handle, hjelp, ...) never
    appearing as known, despite being directly taught across ~785 cards
    in B01-B12/A07/A10/Z01 that happen to have A=="E" (design.md's
    section 4 correction note). Extraction must therefore produce
    segments regardless of what `A` says for those decks, and must NOT
    extract from the 4 confirmed grammar-explanation decks even though
    they also open with an English question (A03/A04/A06/C01, prose
    about genders/pronouns/tone rules, not vocabulary)."""
    segments = import_stock.extract_known_segments(stock_cards)
    by_card = {c["ID"]: c for c in stock_cards}

    decks_with_segments = {by_card[ev["card_id"]]["DECK_ID"] for _segment, ev in segments}
    assert "B02" in decks_with_segments  # A=="E" deck, previously fully excluded
    assert "B05" in decks_with_segments
    assert not decks_with_segments & import_stock._EXCLUDED_PROSE_DECKS

    for _segment, ev in segments:
        assert by_card[ev["card_id"]]["DECK_ID"] not in import_stock._EXCLUDED_PROSE_DECKS


def test_previously_missing_common_vocabulary_is_now_known(stock_cards):
    """The operator's own spot-check of `normalized` directly: these are
    all words taught on A=="E" cards in decks the old A-field-driven
    extraction never read at all."""
    known_by_sig, _ = import_stock.build_known_signatures(stock_cards, {})
    for word in ("trene", "viktig", "handle", "hjelp", "krig", "natt", "dele", "blid", "igjen", "gave"):
        signature = lexeme.build_signature(word, {})
        assert lexeme.signature_key(signature) in known_by_sig, f"{word!r} should be known from stock"


def test_prose_leak_from_grammar_explanation_decks_is_excluded(stock_cards):
    """C01's tone-rules explanation deck has a short, isolated English
    grammar-term fragment ("comparative") that slips under the <=6-word
    segment filter on its own — only the deck-level exclusion catches it
    (design.md's section 4 correction note)."""
    segments = [s for s, _ev in import_stock.extract_known_segments(stock_cards)]
    assert not any("comparative" in s.lower() for s in segments)


def test_stock_strips_parenthetical_asides_in_vocab_fields_but_not_in_c03(stock_cards, judge_fixtures):
    """Two parenthetical uses, handled differently (design.md's section 4
    correction note, found via the operator's own spot-check of the
    skipped set):
    - B05's "(comparative and superlative are not in use)" is a usage
      aside on a regular A=="N" vocab card — must be discarded, or "and"
      leaks into the known-set as if it were Norwegian.
    - C03011's "å late (som om)" has the parenthetical AS the verb's
      defining complement, not an aside — discarding it would silently
      drop a real, already-taught sense ("late som om" = to pretend)
      from the known-set, distinct from bare "late" (C03002)."""
    segments = [s for s, _ev in import_stock.extract_known_segments(stock_cards)]
    assert not any("and" == s.strip().lower() for s in segments)
    assert not any("comparative" in s.lower() for s in segments)

    lemma_map, known_by_sig, known_by_head, denylist = judge_fixtures
    for phrase in ("late", "late til", "late etter", "late som om"):
        signature = lexeme.build_signature(phrase, lemma_map)
        assert lexeme.signature_key(signature) in known_by_sig, f"{phrase!r} should be known from stock"


# ---------------------------------------------------------------------------
# key.py / full-pipeline signature count (task 3.9, deferred here)
# ---------------------------------------------------------------------------


def test_distinct_lexeme_signature_count_matches_measured_baseline(full_pipeline_conn):
    distinct = full_pipeline_conn.execute(
        """
        SELECT COUNT(DISTINCT s.signature_key)
        FROM signature s JOIN normalized n ON n.id = s.normalized_id
        WHERE n.note_type != 'listening'
        """
    ).fetchone()[0]
    assert distinct == import_key.DISTINCT_LEXEME_SIGNATURE_EXPECTED


# ---------------------------------------------------------------------------
# judge.py (tasks 4.5-4.8) — the design D3 regression cases, corrected
# per design.md's implementation-correction note (section 4)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def judge_fixtures(full_pipeline_conn):
    lemma_map = import_key.build_combined_lemma_map(full_pipeline_conn)
    cards = import_stock.load_stock_cards()
    known_by_sig, known_by_head = import_stock.build_known_signatures(cards, lemma_map)
    denylist = import_judge.load_denylist()
    return lemma_map, known_by_sig, known_by_head, denylist


def _verdict(text, judge_fixtures, note_type="word"):
    lemma_map, known_by_sig, known_by_head, denylist = judge_fixtures
    signature = lexeme.build_signature(text, lemma_map)
    return import_judge.judge_one(signature, note_type, denylist, known_by_sig, known_by_head, lemma_map)


@pytest.mark.parametrize(
    "phrase",
    ["bli kvitt", "bli klar over", "bekymre seg", "bestemme seg", "bli lei av"],
)
def test_idioms_entirely_from_known_tokens_still_import(phrase, judge_fixtures):
    verdict, _rule, _evidence = _verdict(phrase, judge_fixtures)
    assert verdict == "import"


@pytest.mark.parametrize(
    "phrase",
    ["gi opp", "regne ut", "dø ut", "legge om", "bytte ut", "låne ut", "finne fram"],
)
def test_known_head_unknown_particle_imports(phrase, judge_fixtures):
    verdict, _rule, _evidence = _verdict(phrase, judge_fixtures)
    assert verdict == "import"


def test_legge_til_imports_despite_stock_teaching_the_legge_family(judge_fixtures):
    verdict, rule, evidence = _verdict("legge til", judge_fixtures)
    assert verdict == "import"


def test_legge_til_noen_i_kopi_is_known_exactly(judge_fixtures):
    verdict, rule, _evidence = _verdict("legge til noen i kopi", judge_fixtures)
    assert verdict == "skip"
    assert rule == "exact-match"


def test_bli_med_is_correctly_skipped_stock_teaches_it_verbatim(judge_fixtures):
    """design.md's implementation-correction note: stock card B13004
    teaches "å bli med" directly, so this is a correct skip, not a false
    one — moved out of the "all import" regression list for this reason."""
    verdict, rule, _evidence = _verdict("bli med", judge_fixtures)
    assert verdict == "skip"
    assert rule == "exact-match"


def test_allerede_is_correctly_skipped_stock_teaches_it_directly(judge_fixtures):
    """design.md's implementation-correction note: stock card B09056
    teaches "allerede" itself, not merely "alle" — correct skip for a
    real reason, unrelated to prefix matching."""
    verdict, rule, _evidence = _verdict("allerede", judge_fixtures)
    assert verdict == "skip"
    assert rule == "exact-match"


def test_aleneforsorger_imports_confirming_no_prefix_match_with_alene(judge_fixtures):
    verdict, _rule, _evidence = _verdict("aleneforsørger", judge_fixtures)
    assert verdict == "import"


def test_and_duck_is_not_auto_skipped(judge_fixtures):
    verdict, _rule, _evidence = _verdict("and", judge_fixtures)
    assert verdict == "import"


def test_denylist_protects_even_a_forced_exact_match(judge_fixtures):
    """The deny-list's actual contract: even if a denylisted lemma WERE in
    the known-set, it must still never produce a skip verdict (task 4.3).
    "and" happens not to be in the known-set under this implementation
    (design.md's correction note) — so this constructs the scenario
    directly rather than relying on that absence."""
    lemma_map, known_by_sig, known_by_head, denylist = judge_fixtures
    signature = ("and", (), False, ())
    forced_known_by_sig = {**known_by_sig, lexeme.signature_key(signature): {"text": "and", "deck_id": "FORCED"}}
    verdict, rule, _evidence = import_judge.judge_one(
        signature, "word", denylist, forced_known_by_sig, known_by_head, lemma_map
    )
    assert verdict == "import"
    assert rule == "denylist-protected"


def test_sentence_shaped_listening_always_imports_regardless_of_match(judge_fixtures):
    lemma_map, known_by_sig, known_by_head, denylist = judge_fixtures
    # a signature that IS in the known-set, but with note_type="listening"
    known_sig_key = next(iter(known_by_sig))
    verdict, rule, _evidence = import_judge.judge_one(
        ("whatever", (), False, ()), "listening", denylist, {known_sig_key: {}}, {}, lemma_map
    )
    assert verdict == "import"
    assert rule == "sentence-shaped"


def test_same_head_different_particle_evidence_references_stock(judge_fixtures):
    verdict, rule, evidence = _verdict("legge til", judge_fixtures)
    assert verdict == "import"
    # "legge til" has particles -> if it also shares a head with known
    # material (it does: bare "legge" is known), the flag path requires
    # cf_stock evidence
    if rule == "same-head-different-particle":
        assert "cf_stock" in evidence


def test_skipped_review_log_is_written(full_pipeline_conn):
    assert import_judge.SKIPPED_REVIEW_LOG_PATH.exists()
    lines = import_judge.SKIPPED_REVIEW_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 0
