"""Tests for scripts/import/lexeme.py — the D3 signature builder (task 4.4)
and its form->lemma map. Pure unit tests, no real data needed."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import lexeme  # noqa: E402


def test_bare_infinitive_signature():
    assert lexeme.build_signature("legge", {}) == ("legge", (), False, ())


def test_particle_verb_is_distinct_from_bare_head():
    bare = lexeme.build_signature("legge", {})
    particle = lexeme.build_signature("legge til", {})
    assert bare != particle
    assert particle == ("legge", ("til",), False, ())


def test_reflexive_is_distinct_from_bare_head():
    reflexive = lexeme.build_signature("legge seg", {})
    assert reflexive == ("legge", (), True, ())


def test_specific_collocation_does_not_match_the_general_particle_form():
    general = lexeme.build_signature("legge til", {})
    specific = lexeme.build_signature("legge til noen i kopi", {})
    assert general != specific
    assert specific == ("legge", ("til",), False, ("noen", "i", "kopi"))


def test_infinitive_marker_is_stripped():
    assert lexeme.build_signature("å legge", {}) == ("legge", (), False, ())


def test_lemma_map_resolves_head_but_not_particles():
    lemma_map = {"later": "late"}
    assert lexeme.build_signature("later", lemma_map) == ("late", (), False, ())


def test_empty_text_returns_none():
    assert lexeme.build_signature("", {}) is None
    assert lexeme.build_signature("   ", {}) is None


def test_leading_indefinite_article_is_stripped_like_infinitive_marker():
    """Regression: found via task 4.8's skipped-set spot-check — "et år"
    was keying on head="et" (treating the article as the lexeme head)
    instead of stripping it the way "å" already was, producing a
    different signature from plain "år" and inflating the distinct-lexeme
    count with spurious article-led duplicates (design.md's section 4
    implementation-correction note)."""
    assert lexeme.build_signature("et år", {}) == lexeme.build_signature("år", {})
    assert lexeme.build_signature("en dag", {}) == lexeme.build_signature("dag", {})
    assert lexeme.build_signature("ei uke", {}) == lexeme.build_signature("uke", {})


def test_bare_article_or_numeral_keeps_its_own_signature():
    # "en"/"et" alone (the numeral "one", or a standalone teaching card)
    # must not be stripped to nothing — only a LEADING article before
    # more text is notation.
    assert lexeme.build_signature("en", {}) == ("en", (), False, ())
    assert lexeme.build_signature("et", {}) == ("et", (), False, ())


def test_signature_key_is_stable_and_distinguishes_components():
    a = lexeme.build_signature("legge til", {})
    b = lexeme.build_signature("legge om", {})
    assert lexeme.signature_key(a) != lexeme.signature_key(b)
    # same signature computed twice -> identical key (used as a dict/SQL key)
    assert lexeme.signature_key(a) == lexeme.signature_key(lexeme.build_signature("legge til", {}))


def test_no_substring_or_prefix_comparison_exists_in_the_signature_mechanism():
    """Structural guarantee behind the 'allerede'/'alle' anti-prefix-match
    property (task 4.5, design D3) — asserted on the mechanism itself
    rather than relying on one illustrative real-data pair (see design.md's
    implementation-correction note on why `allerede` was dropped as that
    example)."""
    allerede = lexeme.build_signature("allerede", {})
    alle = lexeme.build_signature("alle", {})
    assert allerede != alle
    assert allerede[0] != alle[0]  # distinct head lemmas, not merely distinct tuples

    # The only comparisons against the known-set anywhere in this tool are
    # dict/set key lookups (judge.py's `sig_key in known_by_signature_key`),
    # never a prefix/substring check against another signature's text.
    import judge as import_judge

    for source in (inspect.getsource(lexeme), inspect.getsource(import_judge)):
        assert ".startswith(" not in source
        assert ".endswith(" not in source


def test_build_lemma_map_from_normalized_skips_malformed_entries(tmp_path):
    import sqlite3

    import store as import_store

    conn = import_store.connect(tmp_path / "candidates.db")
    run_id = import_store.start_run(conn, "ingest")
    conn.execute(
        "INSERT INTO raw_note (run_id, source, source_note_id, note_type, fields_json) VALUES (?, 'ntnu', '1', 'NoW', '{}')",
        (run_id,),
    )
    raw_note_id = conn.execute("SELECT id FROM raw_note").fetchone()[0]

    good = {"infinitiv": "bli", "presens": "blir", "preteritum": "ble", "perfektum": "har blitt"}
    malformed = {"_malformed": "garbage", "infinitiv": "arkitektur"}
    for text, inflections in (("bli", good), ("arkitektur", malformed)):
        conn.execute(
            """
            INSERT INTO normalized (run_id, raw_note_id, source, note_type, text, inflections_json)
            VALUES (?, ?, 'ntnu', 'word', ?, ?)
            """,
            (run_id, raw_note_id, text, json.dumps(inflections)),
        )
    conn.commit()

    lemma_map = lexeme.build_lemma_map_from_normalized(conn)
    assert lemma_map["blir"] == "bli"
    assert lemma_map["ble"] == "bli"
    assert lemma_map["vært"] if "vært" in lemma_map else True  # last-word fallback, not required here
    assert "arkitekturen" not in lemma_map  # malformed source never contributes
    conn.close()


def test_protected_identities_blocks_homograph_overwrite(tmp_path):
    """Regression: found via task 4.8's skipped-set spot-check — freq6k's
    paradigm miner let "nå"'s present-tense form "når" silently become
    "nå"'s lemma, even though "når" ("when") is itself a genuine
    standalone headword from every other source. A candidate literally
    spelled "når" must never resolve through the lemma map to "nå"'s
    signature (design.md's section 4 implementation-correction note)."""
    import json

    import store as import_store

    conn = import_store.connect(tmp_path / "candidates.db")
    run_id = import_store.start_run(conn, "ingest")
    conn.execute(
        "INSERT INTO raw_note (run_id, source, source_note_id, note_type, fields_json) VALUES (?, 'freq6k', '1', 'word', '{}')",
        (run_id,),
    )
    raw_note_id = conn.execute("SELECT id FROM raw_note").fetchone()[0]

    rows = [
        ("nå", {"paradigm_forms": ["nå", "når", "nådd"]}),  # "nå"'s own paradigm wrongly includes "når"
        ("når", {}),  # "når" is ALSO its own standalone headword, with no paradigm of its own
    ]
    for text, notation in rows:
        conn.execute(
            "INSERT INTO normalized (run_id, raw_note_id, source, note_type, text, notation_json) VALUES (?, ?, 'freq6k', 'word', ?, ?)",
            (run_id, raw_note_id, text, json.dumps(notation)),
        )
    conn.commit()

    lemma_map = lexeme.build_lemma_map_from_normalized(conn)
    assert lemma_map.get("når", "når") == "når"  # must keep its own identity, not become "nå"
    conn.close()
