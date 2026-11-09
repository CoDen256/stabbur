"""Tests for scripts/import/normalize.py — section 3 of bulk-import-anki-csv.

Per-source unit tests don't need the real archives (they test pure parsing
functions directly). The full-pipeline test does need them (to exercise
`run()` against `raw_note` produced by the real ingest), so it's skipped
the same way tests/test_import_ingest.py is when import/ is empty.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import ingest as import_ingest  # noqa: E402
import normalize as import_normalize  # noqa: E402
import store as import_store  # noqa: E402


# ---------------------------------------------------------------------------
# CSV notation parser (task 3.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "word,expected_head",
    [
        ("område /et", "område"),
        ("spå /-dde", "spå"),
        ("fastsette (fastsatte)", "fastsette"),
        ("humle /a/en", "humle"),
        ("maktmisbruk /et/en", "maktmisbruk"),
        ("drive /drev-drevet", "drive"),
        ("være i stand til", "være i stand til"),
    ],
)
def test_strip_csv_notation_reduces_to_lemma_head(word, expected_head):
    head, _notation = import_normalize.strip_csv_notation(word)
    assert head == expected_head


def test_strip_csv_notation_leaves_non_trailing_parens_untouched():
    head, _notation = import_normalize.strip_csv_notation("(eller) ei")
    assert head == "(eller) ei"


def test_strip_csv_notation_flags_complement_placeholder():
    _head, notation = import_normalize.strip_csv_notation("foreta seg noe")
    assert notation.get("has_complement_placeholder") is True


def test_strip_csv_notation_genuine_idiom_is_untouched_and_stays_multiword():
    head, notation = import_normalize.strip_csv_notation("bli kvitt")
    assert head == "bli kvitt"
    assert notation == {}


# ---------------------------------------------------------------------------
# NTNU inflection parser (task 3.3)
# ---------------------------------------------------------------------------


def test_ntnu_well_formed_noun_inflection():
    inflections, pos = import_normalize.parse_ntnu_inflection(
        "en", "antropologi", "antropologien, antropologier, antropologiene"
    )
    assert pos == "substantiv"
    assert inflections == {
        "article": "en",
        "sg_indef": "antropologi",
        "sg_def": "antropologien",
        "pl_indef": "antropologier",
        "pl_def": "antropologiene",
    }


def test_ntnu_mass_noun_single_form_is_not_malformed():
    inflections, pos = import_normalize.parse_ntnu_inflection("en", "bagasje", "bagasjen")
    assert pos == "substantiv"
    assert inflections == {"article": "en", "sg_indef": "bagasje", "sg_def": "bagasjen"}


def test_ntnu_malformed_noun_inflection_surfaces_as_conflict_not_defaulted():
    inflections, pos = import_normalize.parse_ntnu_inflection(
        "en", "arkitektur", "arkitekturen, arkitekturerarkitekturene"
    )
    assert pos == "substantiv"
    assert inflections["_malformed"] == "arkitekturen, arkitekturerarkitekturene"
    assert "pl_indef" not in inflections
    assert "pl_def" not in inflections


def test_ntnu_verb_inflection():
    inflections, pos = import_normalize.parse_ntnu_inflection("å", "bli", "blir, ble, har blitt")
    assert pos == "verb"
    assert inflections == {"infinitiv": "bli", "presens": "blir", "preteritum": "ble", "perfektum": "har blitt"}


def test_ntnu_adjective_inflection():
    inflections, pos = import_normalize.parse_ntnu_inflection("", "gammel", "gammelt, gamle")
    assert pos is None
    assert inflections == {"positiv": "gammel", "nøytrum": "gammelt", "bestemt_flertall": "gamle"}


def test_ntnu_empty_inflection_is_not_malformed():
    inflections, pos = import_normalize.parse_ntnu_inflection("å", "ta ut penger", "")
    assert inflections == {}
    assert pos == "verb"


# ---------------------------------------------------------------------------
# core6k HTML inflection table parser (task 3.4)
# ---------------------------------------------------------------------------


def test_core6k_verb_table():
    html = (
        '<table class="infl"><tbody><tr><td class="l">Infinitive</td><td>å være</td></tr>'
        '<tr><td class="l">Present</td><td>er</td></tr><tr><td class="l">Past</td><td>var</td></tr>'
        '<tr><td class="l">Perfect</td><td>har vært</td></tr></tbody></table>'
    )
    assert import_normalize.parse_core6k_inflection(html) == {
        "infinitiv": "å være",
        "presens": "er",
        "preteritum": "var",
        "perfektum": "har vært",
    }


def test_core6k_noun_table():
    html = (
        '<table class="infl"><tr><td class="l">Singular</td><td>år</td></tr>'
        '<tr><td class="l">Singular def.</td><td>året</td></tr>'
        '<tr><td class="l">Plural</td><td>år</td></tr><tr><td class="l">Plural def.</td><td>årene</td></tr></table>'
    )
    assert import_normalize.parse_core6k_inflection(html) == {
        "sg_indef": "år",
        "sg_def": "året",
        "pl_indef": "år",
        "pl_def": "årene",
    }


def test_core6k_empty_table_is_empty_dict():
    assert import_normalize.parse_core6k_inflection("") == {}


def test_core6k_unrecognized_label_surfaces_as_conflict_not_dropped():
    html = '<table class="infl"><tr><td class="l">Totally Unknown</td><td>x</td></tr></table>'
    result = import_normalize.parse_core6k_inflection(html)
    assert "Totally Unknown" in result["_malformed_labels"]


# ---------------------------------------------------------------------------
# freq6k paradigm mining (task 3.5)
# ---------------------------------------------------------------------------


def test_freq6k_paradigm_forms_extracted_from_embedded_json():
    html = (
        '<template id="r69211-ordpar-paradigm" data-a-cells="31141F">'
        '[["være",["r1sa","være","er","var","vært","vært","værende","vær"]]]</template>'
    )
    forms = import_normalize.parse_freq6k_paradigm(html)
    assert "være" in forms
    assert "er" in forms
    assert "var" in forms
    assert "r1sa" not in forms  # the paradigm code itself, not a surface form


def test_freq6k_paradigm_absent_returns_empty_list_not_error():
    assert import_normalize.parse_freq6k_paradigm("") == []
    assert import_normalize.parse_freq6k_paradigm("<div>no template here</div>") == []


# ---------------------------------------------------------------------------
# Invisible-character normalisation (task 1.4, design D8)
# ---------------------------------------------------------------------------


def test_nbsp_is_normalised_to_a_plain_space():
    assert import_normalize.normalize_invisible_chars("å\xa0starte") == "å starte"


def test_zero_width_characters_are_normalised_by_the_same_rule():
    assert import_normalize.normalize_invisible_chars("et​eple") == "et eple"
    assert import_normalize.normalize_invisible_chars("en﻿etasje") == "en etasje"


def test_normalize_invisible_chars_is_a_noop_on_clean_text():
    assert import_normalize.normalize_invisible_chars("å diskutere") == "å diskutere"


# ---------------------------------------------------------------------------
# A1 Notes field polymorphism (task 3.7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "notes,expected",
    [
        ("/1dʉː/", True),
        ("noun", False),
        ("verb", False),
        ("", False),
        ("conjugated verb", False),
    ],
)
def test_a1_notes_is_ipa(notes, expected):
    assert import_normalize.a1_notes_is_ipa(notes) == expected


# ---------------------------------------------------------------------------
# Part-of-speech mapping (import-pos-lemma-inference, task 1.1-1.4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("noun", "substantiv"),
        ("Noun", "substantiv"),
        ("proper noun", "substantiv"),
        ("adjective", "adjektiv"),
        ("verb", "verb"),
        ("adverb", "adverb"),
        ("preposition", "preposisjon"),
        ("conjunction", "konjunksjon"),
        ("subjunction", "konjunksjon"),
        ("substantiv", "substantiv"),
        ("determiner", None),
        ("set phrase", None),
        ("interjection", None),
        ("pronoun", None),
        ("prefix", None),
        (None, None),
        ("", None),
    ],
)
def test_map_source_pos(value, expected):
    assert import_normalize.map_source_pos(value) == expected


def test_pos_map_output_range_is_subset_of_canonical_values():
    assert set(import_normalize.POS_MAP.values()) <= import_normalize.CANONICAL_POS


# ---------------------------------------------------------------------------
# Part-of-speech inference signals (task 2.1-2.4)
# ---------------------------------------------------------------------------


def test_pos_from_inflection_shape_noun():
    assert import_normalize.pos_from_inflection_shape({"article": "en", "sg_indef": "katt", "pl_def": "kattene"}) == (
        "substantiv"
    )


def test_pos_from_inflection_shape_adjective():
    assert import_normalize.pos_from_inflection_shape({"positiv": "gammel", "komparativ": "eldre"}) == "adjektiv"


def test_pos_from_inflection_shape_does_not_treat_ntnu_blank_article_shape_as_adjective():
    """NTNU's blank-article branch produces this exact shape for an
    articleless *noun* (e.g. "mat", "smør") as well as for a genuine
    adjective, and deliberately leaves `pos` unresolved for it — `positiv`/
    `nøytrum`/`bestemt_flertall` alone must not be treated as adjective
    evidence here, or a real noun gets permanently misfiled (found via the
    task 6.3 spot-check)."""
    assert import_normalize.pos_from_inflection_shape({"positiv": "mat"}) is None
    assert import_normalize.pos_from_inflection_shape({"positiv": "dyr", "nøytrum": "dyrt", "bestemt_flertall": "dyre"}) is None


def test_pos_from_inflection_shape_verb():
    assert import_normalize.pos_from_inflection_shape({"infinitiv": "gå", "presens": "går"}) == "verb"


def test_pos_from_inflection_shape_adverb():
    assert import_normalize.pos_from_inflection_shape({"form": "fort"}) == "adverb"


def test_pos_from_inflection_shape_empty_resolves_to_none():
    assert import_normalize.pos_from_inflection_shape({}) is None


def test_pos_from_inflection_shape_malformed_only_resolves_to_none():
    assert import_normalize.pos_from_inflection_shape({"_malformed": "x"}) is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("å gå", "verb"),
        ("Å SPISE", "verb"),
        ("en katt", "substantiv"),
        ("et hus", "substantiv"),
        ("ei bok", "substantiv"),
        ("EN Katt", "substantiv"),
        ("katt", None),
        ("", None),
        (None, None),
    ],
)
def test_pos_from_text_prefix(text, expected):
    assert import_normalize.pos_from_text_prefix(text) == expected


@pytest.mark.parametrize(
    "translation_text,expected",
    [
        ("to run", "verb"),
        ("To Run", "verb"),
        ("a cat", "substantiv"),
        ("an apple", "substantiv"),
        ("A Cat", "substantiv"),
        ("quickly", None),
        ("", None),
    ],
)
def test_pos_from_translation_prefix(translation_text, expected):
    translations = [{"lang": "en", "text": translation_text}] if translation_text else []
    assert import_normalize.pos_from_translation_prefix(translations) == expected


def test_pos_from_translation_prefix_no_translations():
    assert import_normalize.pos_from_translation_prefix([]) is None


def test_freq6k_pos_is_mapped_to_canonical_not_passed_through():
    result = import_normalize._normalize_freq6k({"Norwegian word": "katt", "Word class": "noun"})
    assert result["pos"] == "substantiv"


def test_freq6k_unmappable_pos_resolves_to_none():
    result = import_normalize._normalize_freq6k({"Norwegian word": "den", "Word class": "determiner"})
    assert result["pos"] is None


# ---------------------------------------------------------------------------
# Lemma derivation (task 4.1-4.2, design D5) — parity with ui/ui.js's
# deriveLemmaGuess, the function actually wired to the editor's "From
# text" action.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("å spise", "spise"),
        ("en katt", "katt"),
        ("et hus", "hus"),
        ("ei bok", "bok"),
        ("gi opp", "gi"),
        ("katt", "katt"),
        ("", ""),
        ("å gi opp", "gi"),
    ],
)
def test_derive_lemma(text, expected):
    assert import_normalize.derive_lemma(text) == expected


# ---------------------------------------------------------------------------
# Full pipeline against the real archives
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not all((import_ingest.IMPORT_DIR / spec["file"]).exists() for spec in import_ingest.APKG_SOURCES.values()),
    reason="import/ source archives are gitignored and not present in this checkout",
)


@pytest.fixture
def ingested_conn(tmp_path):
    conn = import_store.connect(tmp_path / "candidates.db")
    run_id = import_store.start_run(conn, "ingest")
    import_ingest.run(conn, run_id)
    yield conn
    conn.close()


def test_normalize_matches_measured_csv_split(ingested_conn):
    run_id = import_store.start_run(ingested_conn, "normalize")
    import_normalize.run(ingested_conn, run_id)

    counts = dict(
        ingested_conn.execute(
            "SELECT note_type, COUNT(*) FROM normalized WHERE source = 'herpaberget' GROUP BY note_type"
        ).fetchall()
    )
    assert counts == {"word": 826, "expression": 326}


def test_normalize_matches_measured_a1_type_split(ingested_conn):
    run_id = import_store.start_run(ingested_conn, "normalize")
    import_normalize.run(ingested_conn, run_id)

    counts = dict(
        ingested_conn.execute(
            "SELECT note_type, COUNT(*) FROM normalized WHERE source = 'a1_31k' GROUP BY note_type"
        ).fetchall()
    )
    assert counts == {"word": 1624, "listening": 1473}


def test_normalize_a1_ipa_transcription_count_matches_measured(ingested_conn):
    run_id = import_store.start_run(ingested_conn, "normalize")
    import_normalize.run(ingested_conn, run_id)

    count = ingested_conn.execute(
        "SELECT COUNT(*) FROM normalized WHERE source = 'a1_31k' AND transcription IS NOT NULL"
    ).fetchone()[0]
    assert count == 52


def test_normalize_freq6k_pos_distribution_matches_measured(ingested_conn):
    """Task 1.2: freq6k's raw English `Word class` is mapped to its
    canonical Norwegian equivalent at normalize time (not passed through
    unchanged). `substantiv` is 2,165 (not design.md's `noun`-only 2,163)
    because `proper noun` (2) also maps to `substantiv` — measured, not
    assumed, same convention this module already follows elsewhere."""
    run_id = import_store.start_run(ingested_conn, "normalize")
    import_normalize.run(ingested_conn, run_id)

    counts = dict(
        ingested_conn.execute(
            "SELECT pos, COUNT(*) FROM normalized WHERE source = 'freq6k' GROUP BY pos ORDER BY COUNT(*) DESC"
        ).fetchall()
    )
    assert counts["substantiv"] == 2165
    assert counts["verb"] == 687
    assert counts["adjektiv"] == 662
    assert set(counts) - {None} <= import_normalize.CANONICAL_POS


def test_normalize_is_idempotent_on_rerun(ingested_conn):
    run_id_1 = import_store.start_run(ingested_conn, "normalize")
    import_normalize.run(ingested_conn, run_id_1)
    first_count = ingested_conn.execute("SELECT COUNT(*) FROM normalized").fetchone()[0]

    run_id_2 = import_store.start_run(ingested_conn, "normalize")
    import_normalize.run(ingested_conn, run_id_2)
    second_count = ingested_conn.execute("SELECT COUNT(*) FROM normalized").fetchone()[0]

    assert first_count == second_count
    assert ingested_conn.execute(
        "SELECT COUNT(*) FROM normalized WHERE run_id = ?", (run_id_1,)
    ).fetchone()[0] == 0


def test_normalize_does_not_touch_raw_note(ingested_conn):
    before = ingested_conn.execute("SELECT COUNT(*) FROM raw_note").fetchone()[0]
    run_id = import_store.start_run(ingested_conn, "normalize")
    import_normalize.run(ingested_conn, run_id)
    after = ingested_conn.execute("SELECT COUNT(*) FROM raw_note").fetchone()[0]
    assert before == after


def test_normalize_leaves_no_nbsp_in_text(ingested_conn):
    """Task 1.4/1.5: the 140 article+NBSP+word rows design.md measured are
    fixed, and fixing them changes no signature/verdict downstream (`\\s`
    already matched U+00A0, so article-stripping and `head_lemma` were
    never affected — a verdict diff here would mean something else moved,
    not this fix)."""
    run_id = import_store.start_run(ingested_conn, "normalize")
    import_normalize.run(ingested_conn, run_id)
    count = ingested_conn.execute("SELECT COUNT(*) FROM normalized WHERE text LIKE '%' || CHAR(160) || '%'").fetchone()[
        0
    ]
    assert count == 0


def test_normalize_nbsp_fix_does_not_change_signature():
    """Task 1.5: `\\s` already matched U+00A0, so the signature a
    once-NBSP-carrying row produces is identical to the clean row's — the
    fix changes `text`, not what `key` derives from it."""
    import lexeme

    lemma_map: dict[str, str] = {}
    clean = import_normalize.normalize_invisible_chars("å eple")
    was_nbsp = import_normalize.normalize_invisible_chars("å\xa0eple")
    assert clean == was_nbsp == "å eple"
    assert lexeme.build_signature(clean, lemma_map) == lexeme.build_signature("å\xa0eple", lemma_map)
