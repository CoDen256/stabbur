"""Tests for review-queue-filters: scripts/import/{normalize,judge,push,
audit}.py.

Most of these are deliberately *not* gated on the real stock bundle or
import archives — the new rules this change adds (sections 2-7) only need
a known-token/known-ngram set, which these tests fabricate directly,
exercising the real `judge_one` logic without depending on
`STABBUR_IMPORT_STOCK_BUNDLE` (unavailable in this checkout, same
limitation design.md records for the pos-lemma-inference change). The
section 9 full-corpus numbers (the ~571/~262 figures) can only be
re-verified end to end once that bundle is available — see design.md's
task 9.6 note.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import audit as import_audit  # noqa: E402
import ingest as import_ingest  # noqa: E402
import judge as import_judge  # noqa: E402
import merge as import_merge  # noqa: E402
import normalize as import_normalize  # noqa: E402
import push as import_push  # noqa: E402
import store as import_store  # noqa: E402

_HAS_SOURCES = all((import_ingest.IMPORT_DIR / spec["file"]).exists() for spec in import_ingest.APKG_SOURCES.values())


# ---------------------------------------------------------------------------
# normalize.is_sentence_shaped (tasks 2.2/3.1, design D1/D7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Jeg er norsk",
        "Er du norsk?",
        "Han bor i Norge",
        "Jeg kommer fra Frankrike",
        "Hvor er nærmeste sykehus?",
        "Jeg lærer norsk.",
    ],
)
def test_sentence_shaped_capital_with_corroboration(text):
    assert import_normalize.is_sentence_shaped(text)


@pytest.mark.parametrize(
    "text",
    [
        "gi opp",
        "bli klar over",
        "i gamle dager",
        "å gå på tur",
        "",
        None,
        "katt",
    ],
)
def test_not_sentence_shaped_lowercase_or_single_token(text):
    assert not import_normalize.is_sentence_shaped(text)


def test_hard_lowercase_guard_regardless_of_word_count():
    """Task 3.3 (design D1): a lowercase candidate is never sentence-shaped
    at any word count — the guard that keeps `ta skjeen i en annen hånd`
    out of the fully-known-sentence rule."""
    assert not import_normalize.is_sentence_shaped("ta skjeen i en annen hånd")
    assert not import_normalize.is_sentence_shaped("få endene til å møtes")


def test_country_name_is_not_sentence_shaped():
    """Measured while tuning the core6k re-routing (task 2.3): a
    capitalised multiword proper noun has neither sentence punctuation nor
    a pronoun/interrogative token, so it is not sentence-shaped."""
    assert not import_normalize.is_sentence_shaped("San Marino")
    assert not import_normalize.is_sentence_shaped("New Zealand")
    assert not import_normalize.is_sentence_shaped("De forente stater")
    assert not import_normalize.is_sentence_shaped("Den demokratiske republikken Kongo")


def test_single_capitalised_token_is_not_sentence_shaped():
    """A single capitalised token is a proper-noun candidate (design D3),
    not a sentence — `is_sentence_shaped` requires multiword too."""
    assert not import_normalize.is_sentence_shaped("Barcelona")


# ---------------------------------------------------------------------------
# core6k mistyped-sentence re-routing (tasks 2.1/2.3, design D7)
# ---------------------------------------------------------------------------


def test_core6k_sentence_in_word_field_is_retyped_to_listening():
    fields = {"Norwegian-Word": "Hvor er nærmeste sykehus?", "English-Word": "Where is the nearest hospital?"}
    result = import_normalize._normalize_core6k(fields)
    assert result["note_type"] == "listening"


def test_core6k_genuine_single_word_stays_word():
    fields = {"Norwegian-Word": "sykehus", "English-Word": "hospital"}
    result = import_normalize._normalize_core6k(fields)
    assert result["note_type"] == "word"


def test_core6k_country_name_stays_word_not_listening():
    """Task 2.3: no genuine single-word or expression candidate moves with
    the sentences — a country name is multiword and capitalised but is not
    a sentence."""
    fields = {"Norwegian-Word": "San Marino", "English-Word": "San Marino"}
    result = import_normalize._normalize_core6k(fields)
    assert result["note_type"] == "word"


def test_hvor_er_naermeste_sykehus_retyped_then_skipped_end_to_end():
    """Task 8.8: the operator's original example, end to end — re-typed by
    `_normalize_core6k` (section 2), then skipped by the fully-known-
    sentence rule (section 3) once every word in it is known."""
    fields = {"Norwegian-Word": "Hvor er nærmeste sykehus?", "English-Word": "Where is the nearest hospital?"}
    normalized = import_normalize._normalize_core6k(fields)
    assert normalized["note_type"] == "listening"

    text = normalized["text"]
    known_tokens = _known("hvor", "er", "nærmeste", "sykehus")
    tokens = tuple(w.strip("?").lower() for w in text.split())
    signature = (tokens[0], (), False, tokens[1:])
    verdict, rule, _evidence = import_judge.judge_one(
        text, signature, frozenset(), known_tokens, {}, {}, {}, {}, note_type=normalized["note_type"],
    )
    assert verdict == "skip"
    assert rule == "fully-known-sentence"


@pytest.mark.skipif(not _HAS_SOURCES, reason="needs import/ source archives, not tracked in git")
def test_core6k_sentence_rerouting_count_against_real_archives():
    """Task 2.1/2.3's own measured count: design.md's illustrative "23
    known rows" was not exhaustive — measured directly against this
    bundle's full core6k deck, 54 rows actually qualify (see design.md's
    task 2.3 re-measurement note)."""
    conn = import_store.connect(":memory:")
    run_id = import_store.start_run(conn, "ingest")
    import_ingest.run(conn, run_id)
    rows = conn.execute("SELECT fields_json FROM raw_note WHERE source = 'core6k'").fetchall()
    matches = [
        json.loads(r["fields_json"])["Norwegian-Word"].strip()
        for r in rows
        if import_normalize.is_sentence_shaped(json.loads(r["fields_json"]).get("Norwegian-Word", "").strip())
    ]
    assert len(matches) == 54
    assert "Hvor er nærmeste sykehus?" in matches
    assert "San Marino" not in matches


# ---------------------------------------------------------------------------
# judge.is_pure_numeral (task 4.3, design D3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["tjuefire", "ni hundre", "titusen", "tjuesjuende", "tjueen", "hundretusen"])
def test_numeral_expressions_match_whole_text(text):
    assert import_judge.is_pure_numeral(text)


@pytest.mark.parametrize(
    "text",
    [
        "en passkontroll",
        "en",
        "et",
        "ei",
        "tre",
        "passkontroll",
        "",
        None,
    ],
)
def test_numeral_rule_never_matches_substring_or_bare_ambiguous_word(text):
    """Task 4.3: an earlier attempt matched any text containing a number
    word and returned 1,564 hits including `en passkontroll` — this must
    match the whole text only, and the bare ambiguous forms must never
    match on their own."""
    assert not import_judge.is_pure_numeral(text)


def test_numeral_fused_compound_is_unambiguous():
    """`tjueen` fuses "tjue"+"en" into one token — unlike bare `en`, there
    is no article reading of this string, so it is safe to match."""
    assert import_judge.is_pure_numeral("tjueen")


# ---------------------------------------------------------------------------
# judge.classify_lexical_item (tasks 4.1/4.2/4.4, design D3)
# ---------------------------------------------------------------------------


def test_proper_noun_both_capitalised():
    rule, _evidence = import_judge.classify_lexical_item("Barcelona", [{"lang": "en", "text": "Barcelona"}])
    assert rule == "proper-noun"


def test_derived_from_proper_noun_lowercase_text_capitalised_gloss():
    rule, _evidence = import_judge.classify_lexical_item("italiensk", [{"lang": "en", "text": "Italian"}])
    assert rule == "derived-from-proper-noun"


def test_neither_capitalised_is_not_classified():
    assert import_judge.classify_lexical_item("katt", [{"lang": "en", "text": "cat"}]) is None


def test_god_dag_sentence_gloss_capital_is_not_a_proper_noun():
    """Task 4.4: the gloss-capitalisation test over a sentence returns
    false hits (`God dag!` -> `Good day!`) if it isn't restricted to
    `type=word` — verified at the `judge_one` level since that's where the
    note_type restriction actually lives."""
    verdict, rule, _evidence = import_judge.judge_one(
        "God dag!",
        ("god dag", (), False, ()),
        frozenset(),
        {},
        {},
        {},
        {},
        {},
        note_type="listening",
        translations=[{"lang": "en", "text": "Good day!"}],
    )
    assert rule not in ("proper-noun", "derived-from-proper-noun")


# ---------------------------------------------------------------------------
# judge_one: the fully-known-sentence rule (tasks 3.1-3.6, design D1/D2)
# ---------------------------------------------------------------------------


def _known(*words: str) -> dict[str, dict]:
    return {w: {"evidence": True} for w in words}


def test_fully_known_sentence_skips():
    known_tokens = _known("jeg", "er", "norsk", "du", "han", "bor", "i", "norge", "kommer", "fra", "frankrike")
    for text in ("Jeg er norsk", "Han bor i Norge", "Jeg kommer fra Frankrike"):
        tokens = tuple(w.strip("?.!").lower() for w in text.split())
        signature = (tokens[0], (), False, tokens[1:])
        verdict, rule, _evidence = import_judge.judge_one(
            text, signature, frozenset(), known_tokens, {}, {}, {}, {},
        )
        assert verdict == "skip", text
        assert rule == "fully-known-sentence"


def test_lowercase_idiom_with_all_known_tokens_still_imports():
    """Task 8.2 — the rule's reason for existing: every one of these must
    import despite every token being known, because none is capitalised."""
    phrases = [
        "gi opp", "bli klar over", "bli lei av", "dø ut", "legge om", "bytte ut",
        "trekke ut", "vokse opp", "grue seg", "ta hensyn til", "gå i vasken",
        "ta skjeen i en annen hånd", "få endene til å møtes", "ta noe for god fisk",
        "å gå på tur", "å ta det med ro", "i gamle dager",
    ]
    all_words = {w for phrase in phrases for w in phrase.lower().replace("å ", "").split()}
    known_tokens = _known(*all_words)
    for phrase in phrases:
        tokens = tuple(w.lower() for w in phrase.replace("å ", "").split())
        if len(tokens) < 2:
            continue
        signature = (tokens[0], (), False, tokens[1:])
        verdict, rule, _evidence = import_judge.judge_one(
            phrase, signature, frozenset(), known_tokens, {}, {}, {}, {},
        )
        assert verdict == "import", phrase
        assert rule != "fully-known-sentence"


def test_capitalised_candidate_with_one_unknown_word_imports():
    """Task 8.3."""
    known_tokens = _known("jeg", "kommer", "fra")
    text = "Jeg kommer fra Timbuktu"
    tokens = tuple(w.lower() for w in text.split())
    signature = (tokens[0], (), False, tokens[1:])
    verdict, rule, _evidence = import_judge.judge_one(text, signature, frozenset(), known_tokens, {}, {}, {}, {})
    assert verdict == "import"
    assert rule != "fully-known-sentence"


def test_fully_known_sentence_with_audio_skipped_by_default():
    """Task 8.4/D2: no audio condition by default."""
    known_tokens = _known("jeg", "er", "norsk")
    text = "Jeg er norsk"
    signature = ("jeg", (), False, ("er", "norsk"))
    verdict, rule, _evidence = import_judge.judge_one(
        text, signature, frozenset(), known_tokens, {}, {}, {}, {}, audio_ref="recording.mp3",
    )
    assert verdict == "skip"
    assert rule == "fully-known-sentence"


def test_audio_condition_can_be_enabled_for_the_sensitivity_report():
    """Task 3.4/5.5: with the audio condition on, a fully-known sentence
    that has a recording imports instead."""
    known_tokens = _known("jeg", "er", "norsk")
    text = "Jeg er norsk"
    signature = ("jeg", (), False, ("er", "norsk"))
    verdict, rule, _evidence = import_judge.judge_one(
        text, signature, frozenset(), known_tokens, {}, {}, {}, {},
        audio_ref="recording.mp3", require_no_audio_for_sentence_rule=True,
    )
    assert verdict == "import"
    assert rule != "fully-known-sentence"

    # No audio -> still skips even with the condition enabled.
    verdict, rule, _evidence = import_judge.judge_one(
        text, signature, frozenset(), known_tokens, {}, {}, {}, {},
        audio_ref=None, require_no_audio_for_sentence_rule=True,
    )
    assert verdict == "skip"
    assert rule == "fully-known-sentence"


def test_numeral_rule_via_judge_one():
    for text in ("tjuefire", "ni hundre"):
        verdict, rule, _evidence = import_judge.judge_one(
            text, (text, (), False, ()), frozenset(), {}, {}, {}, {}, {}, note_type="word",
        )
        assert verdict == "skip", text
        assert rule == "numeral"


def test_en_passkontroll_not_skipped_as_numeral():
    """Task 8.5."""
    verdict, rule, _evidence = import_judge.judge_one(
        "en passkontroll", ("passkontroll", (), False, ()), frozenset(), {}, {}, {}, {}, {}, note_type="word",
    )
    assert rule != "numeral"


# ---------------------------------------------------------------------------
# Decision precedence (tasks 6.1-6.3, design D4)
# ---------------------------------------------------------------------------


def test_apply_new_rules_false_never_triggers_a_new_rule():
    """Task 6.1/6.2: a decided candidate's data is run with
    `apply_new_rules=False`, so none of the new rules can flip it."""
    known_tokens = _known("jeg", "er", "norsk")
    text = "Jeg er norsk"
    signature = ("jeg", (), False, ("er", "norsk"))
    verdict, rule, _evidence = import_judge.judge_one(
        text, signature, frozenset(), known_tokens, {}, {}, {}, {}, apply_new_rules=False,
    )
    assert rule != "fully-known-sentence"

    verdict, rule, _evidence = import_judge.judge_one(
        "tjuefire", ("tjuefire", (), False, ()), frozenset(), {}, {}, {}, {}, {},
        note_type="word", apply_new_rules=False,
    )
    assert rule != "numeral"


def test_run_exempts_decided_signatures_from_new_rules(monkeypatch, tmp_path):
    """Task 6.1/6.3 at the `run()` level: a signature carrying a decision
    is judged with `apply_new_rules=False`, so a re-run never flips its
    verdict to a new-rule skip — verified against an in-memory store with
    a fabricated known-set (stock.py itself is monkeypatched out, so this
    needs no real bundle)."""
    conn = import_store.connect(tmp_path / "test.db")

    # One sentence candidate, fully known, which the new rule would skip.
    run_id = import_store.start_run(conn, "ingest")
    conn.execute(
        "INSERT INTO raw_note (run_id, source, source_note_id, note_type, fields_json) VALUES (?, 'ntnu', '1', 'listening', '{}')",
        (run_id,),
    )
    normalized_id = conn.execute(
        """
        INSERT INTO normalized (run_id, raw_note_id, source, note_type, text, pos, translations_json, inflections_json, order_signal_json, notation_json)
        VALUES (?, 1, 'ntnu', 'listening', 'Jeg er norsk', NULL, '[]', '{}', '{}', '{}')
        """,
        (run_id,),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO signature (run_id, normalized_id, signature_key, head_lemma, particles_json, reflexive, complements_json)
        VALUES (?, ?, 'sig-1', 'jeg', '[]', 0, '["er", "norsk"]')
        """,
        (run_id, normalized_id),
    )
    conn.execute(
        "INSERT INTO decision (signature_key, decision, decided_at) VALUES ('sig-1', 'accept', '2026-01-01T00:00:00Z')"
    )
    conn.commit()

    monkeypatch.setattr(import_judge, "build_known_set_context", lambda conn: {
        "lemma_map": {},
        "known_tokens": _known("jeg", "er", "norsk"),
        "known_tokens_strong": {},
        "known_ngrams": {},
        "known_by_head_lemma": {},
        "denylist": frozenset(),
    })

    run_id = import_store.start_run(conn, "judge")
    import_judge.run(conn, run_id)

    verdict_row = conn.execute("SELECT verdict, rule FROM verdict WHERE signature_key = 'sig-1'").fetchone()
    assert verdict_row["rule"] != "fully-known-sentence"
    assert verdict_row["verdict"] == "import"


# ---------------------------------------------------------------------------
# Push ordering (tasks 7.1/7.2, design D6)
# ---------------------------------------------------------------------------


def test_push_emits_in_review_order(monkeypatch, tmp_path):
    """Task 8.9: push order matches review order over a multi-candidate
    fixture — `push_one` is monkeypatched to avoid any real HTTP call."""
    conn = import_store.connect(tmp_path / "test.db")
    run_id = import_store.start_run(conn, "merge")

    pushed_order = []
    monkeypatch.setattr(import_push, "push_one", lambda conn, row, run_id: pushed_order.append(row["signature_key"]))

    # Insert three candidates out of order, with distinct frequency_index.
    for sig, freq in [("low-freq", 500), ("high-freq", 5), ("mid-freq", 50)]:
        conn.execute(
            """
            INSERT INTO candidate (run_id, signature_key, fields_json, order_key_json, verdict)
            VALUES (?, ?, '{}', ?, 'import')
            """,
            (run_id, sig, json.dumps({"frequency_index": freq, "core6k_rank": None, "cefr": None, "chapter": None})),
        )
        conn.execute(
            "INSERT INTO decision (signature_key, decision, decided_at) VALUES (?, 'accept', '2026-01-01T00:00:00Z')",
            (sig,),
        )
    conn.commit()

    import_push.run(conn, run_id=run_id)
    assert pushed_order == ["high-freq", "mid-freq", "low-freq"]


def test_interrupted_and_resumed_push_still_emits_in_review_order(monkeypatch, tmp_path):
    """Task 7.2."""
    conn = import_store.connect(tmp_path / "test.db")
    run_id = import_store.start_run(conn, "merge")
    for sig, freq in [("low-freq", 500), ("high-freq", 5), ("mid-freq", 50)]:
        conn.execute(
            "INSERT INTO candidate (run_id, signature_key, fields_json, order_key_json, verdict) VALUES (?, ?, '{}', ?, 'import')",
            (run_id, sig, json.dumps({"frequency_index": freq, "core6k_rank": None, "cefr": None, "chapter": None})),
        )
        conn.execute(
            "INSERT INTO decision (signature_key, decision, decided_at) VALUES (?, 'accept', '2026-01-01T00:00:00Z')",
            (sig,),
        )
    # Simulate "high-freq" already pushed in an earlier, interrupted run.
    conn.execute("UPDATE candidate SET note_id = 'already-pushed' WHERE signature_key = 'high-freq'")
    conn.commit()

    pushed_order = []
    monkeypatch.setattr(import_push, "push_one", lambda conn, row, run_id: pushed_order.append(row["signature_key"]))
    import_push.run(conn, run_id=run_id)
    assert pushed_order == ["mid-freq", "low-freq"]


# ---------------------------------------------------------------------------
# The eligibility audit (tasks 5.1-5.6, design D5)
# ---------------------------------------------------------------------------


def _seed_candidate(conn, signature_key, text, note_type="word", verdict="import", rule=None, translations=None):
    run_id = import_store.start_run(conn, "merge")
    fields = {"note_type": note_type, "text": text, "translations": translations or []}
    conn.execute(
        """
        INSERT INTO candidate (run_id, signature_key, fields_json, verdict, verdict_evidence_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, signature_key, json.dumps(fields), verdict, json.dumps({"rule": rule})),
    )


def test_audit_totals_and_per_rule(tmp_path):
    conn = import_store.connect(tmp_path / "test.db")
    _seed_candidate(conn, "sig-1", "Jeg er norsk", note_type="listening", verdict="skip", rule="fully-known-sentence")
    _seed_candidate(conn, "sig-2", "Barcelona", verdict="skip", rule="proper-noun")
    _seed_candidate(conn, "sig-3", "katt", verdict="import")
    conn.commit()

    baseline_snapshot = {"signature_keys": ["sig-1", "sig-2", "sig-3"], "total_import": 3, "per_type": {}}
    totals, per_rule = import_audit.build_totals_and_per_rule(conn, baseline_snapshot)

    assert totals == {"before": 3, "after": 1, "delta": 2, "newly_skipped": 2}
    assert per_rule["fully-known-sentence"]["count"] == 1
    assert per_rule["proper-noun"]["count"] == 1
    assert per_rule["proper-noun"]["candidates"][0]["text"] == "Barcelona"


def test_audit_disagreements_reports_without_changing_decision(monkeypatch, tmp_path):
    """Task 5.4/D4: a new rule disagreeing with an accepted decision is
    reported, not acted on."""
    conn = import_store.connect(tmp_path / "test.db")
    run_id = import_store.start_run(conn, "ingest")
    conn.execute(
        "INSERT INTO raw_note (run_id, source, source_note_id, note_type, fields_json) VALUES (?, 'ntnu', '1', 'listening', '{}')",
        (run_id,),
    )
    normalized_id = conn.execute(
        """
        INSERT INTO normalized (run_id, raw_note_id, source, note_type, text, translations_json, inflections_json, order_signal_json, notation_json)
        VALUES (?, 1, 'ntnu', 'listening', 'Jeg er norsk', '[]', '{}', '{}', '{}')
        """,
        (run_id,),
    ).lastrowid
    conn.execute(
        "INSERT INTO signature (run_id, normalized_id, signature_key, head_lemma, particles_json, reflexive, complements_json) VALUES (?, ?, 'sig-1', 'jeg', '[]', 0, '[\"er\", \"norsk\"]')",
        (run_id, normalized_id),
    )
    conn.execute("INSERT INTO decision (signature_key, decision, decided_at) VALUES ('sig-1', 'accept', '2026-01-01T00:00:00Z')")
    conn.commit()

    monkeypatch.setattr(import_audit.judge_stage, "build_known_set_context", lambda conn: {
        "lemma_map": {}, "known_tokens": _known("jeg", "er", "norsk"), "known_tokens_strong": {},
        "known_ngrams": {}, "known_by_head_lemma": {}, "denylist": frozenset(),
    })

    disagreements = import_audit.build_disagreements(conn)
    assert len(disagreements) == 1
    assert disagreements[0]["would_skip_rule"] == "fully-known-sentence"

    # Decision itself must be untouched.
    decision = conn.execute("SELECT decision FROM decision WHERE signature_key = 'sig-1'").fetchone()
    assert decision["decision"] == "accept"


def test_audit_recover_flips_verdict_without_touching_decision(tmp_path):
    """Task 5.6."""
    conn = import_store.connect(tmp_path / "test.db")
    _seed_candidate(conn, "sig-1", "Jeg er norsk", verdict="skip", rule="fully-known-sentence")
    conn.commit()

    recovered = import_audit.recover(conn, "sig-1")
    assert recovered is True
    row = conn.execute("SELECT verdict FROM candidate WHERE signature_key = 'sig-1'").fetchone()
    assert row["verdict"] == "import"


def test_audit_recover_returns_false_for_unknown_signature(tmp_path):
    conn = import_store.connect(tmp_path / "test.db")
    assert import_audit.recover(conn, "does-not-exist") is False
