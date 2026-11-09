"""
scripts/import/judge.py — section 4b: `signature` + D13 known-set ->
`verdict`. Rewritten under design D13 (tasks 4b.7, 4b.8, 4b.11); supersedes
the exact-signature-match rule this module used to implement (tasks
4.5-4.8, left in tasks.md section 4 as a record of what was built and what
it cost — see that section's own warning not to use it as a spec).

A candidate is skipped iff (D13's own statement of the rule):
- single-word: its own lemma is in `KNOWN_TOKENS`
- multiword: its own full surface sequence is in `KNOWN_NGRAMS`

Nothing else skips. In particular `note_type == "listening"` no longer
forces an import (task 4b.11, superseding task 4.6's "sentence-shaped"
rule) — a1_31k's sentence candidates are attestation-checked exactly like
single words and phrases; some of them genuinely are attested and must
skip.

There is still no substring, prefix, head-only, or token-subset comparison
anywhere in this module (D3's prohibitions survive D13 verbatim, per
design.md) — the only lookups against the known-set are dict/set
membership checks on a candidate's own full token sequence.

Deny-list ordering (D13.4, task 4b.8): the deny-list is consulted *after*
the known-set check, and only for "weak" single-token evidence (attested
only inside a longer line, never as its own dedicated one-word card) — it
must never override "strong" evidence (`KNOWN_TOKENS_STRONG`, a dedicated
card teaching exactly that word) or a multiword n-gram match. This is the
opposite of the old D5-era ordering, which checked the deny-list *before*
any match and so blocked every one of its entries unconditionally,
including the 11 that stock legitimately teaches as their own cards.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import key as key_stage
import lexeme
import normalize
import stock

DENYLIST_PATH = Path(__file__).resolve().parent / "denylist.json"
SKIPPED_REVIEW_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "import" / "skipped_review.jsonl"


def load_denylist() -> frozenset[str]:
    data = json.loads(DENYLIST_PATH.read_text(encoding="utf-8"))
    return frozenset(data["lemmas"])


# ---------------------------------------------------------------------------
# Proper nouns, nationalities, numerals (review-queue-filters tasks 4.1-4.6,
# design D3). Restricted to single-token `type=word` candidates by the
# caller (judge_one only reaches these inside its `len(tokens) == 1`
# branch) — the same gloss-capitalisation test over sentence-shaped
# candidates returns 1,194 false hits (`God dag!` -> `Good day!`), so a
# sentence-initial capital must never be read as a proper noun.
# ---------------------------------------------------------------------------

_NUMERAL_UNITS = (
    "null", "en", "to", "tre", "fire", "fem", "seks", "sju", "syv", "åtte", "ni", "ti",
    "elleve", "tolv", "tretten", "fjorten", "femten", "seksten", "sytten", "atten", "nitten",
)
_NUMERAL_TENS = ("tjue", "tretti", "førti", "femti", "seksti", "sytti", "åtti", "nitti")
_NUMERAL_SCALES = ("hundre", "tusen", "million", "millioner", "milliard", "milliarder")
_ORDINAL_UNITS = (
    "nullte", "første", "andre", "tredje", "fjerde", "femte", "sjette", "sjuende", "syvende",
    "åttende", "niende", "tiende", "ellevte", "tolvte", "trettende", "fjortende", "femtende",
    "sekstende", "syttende", "attende", "nittende",
)
_ORDINAL_TENS = ("tjuende", "trettiende", "førtiende", "femtiende", "sekstiende", "syttiende", "åttiende", "nittiende")


def _build_numeral_expression_words() -> frozenset[str]:
    """Every single-token Norwegian number word or ordinal this bundle's
    numerals are built from (task 4.3), including the one-word compounds
    Bokmål spelling uses for 21-99 (`tjueen`, `syttisju`) and their
    ordinals (`tjuesjuende`)."""
    words = set(_NUMERAL_UNITS) | set(_NUMERAL_TENS) | set(_NUMERAL_SCALES) | set(_ORDINAL_TENS)
    words.update({"titusen", "hundretusen"})
    for tens in _NUMERAL_TENS:
        for unit in _NUMERAL_UNITS[1:11]:
            words.add(tens + unit)
        for ordinal_unit in _ORDINAL_UNITS[1:11]:
            words.add(tens + ordinal_unit)
    return frozenset(words)


NUMERAL_EXPRESSION_WORDS = _build_numeral_expression_words()

# Task 4.3: `en`/`et`/`ei` (indefinite articles) and `tre` (the noun/verb
# homograph flagged in design.md's risk section) are ambiguous only as a
# *bare standalone* token — fused into a longer numeral (`tjueen`) there is
# no ambiguity, so only the bare forms are excluded here.
_AMBIGUOUS_BARE_NUMERALS = frozenset({"en", "et", "ei", "tre"})


def is_pure_numeral(text: str | None) -> bool:
    """Task 4.3 (design D3): the WHOLE text must be a number expression,
    never a substring — an earlier attempt matched any text containing a
    number word and returned 1,564 hits including `en passkontroll`
    (`en` is both the numeral "one" and the indefinite article)."""
    if not text:
        return False
    stripped = text.strip()
    tokens = [tok.lower() for tok in stripped.split()]
    if not tokens:
        return False
    if len(tokens) == 1 and tokens[0] in _AMBIGUOUS_BARE_NUMERALS:
        return False
    return all(tok in NUMERAL_EXPRESSION_WORDS for tok in tokens)


def _translation_capitalized(translations: list[dict] | None) -> bool:
    for translation in translations or []:
        text = (translation.get("text") or "").strip()
        if text and text[:1].isupper():
            return True
    return False


def classify_lexical_item(text: str, translations: list[dict] | None) -> tuple[str, dict] | None:
    """Tasks 4.1/4.2: proper noun (both capitalised) and derived-from-
    proper-noun (lowercase text, capitalised gloss) — the numeral check
    (task 4.3) is handled separately in `judge_one` since it isn't limited
    to single tokens. Returns (rule, evidence) or None."""
    text_capitalized = bool(text) and text[:1].isupper()
    gloss_capitalized = _translation_capitalized(translations)
    if text_capitalized and gloss_capitalized:
        return "proper-noun", {"text": text, "translations": translations}
    if not text_capitalized and gloss_capitalized:
        return "derived-from-proper-noun", {"text": text, "translations": translations}
    return None


def judge_one(
    text: str,
    signature: tuple,
    denylist: frozenset[str],
    known_tokens: dict[str, dict],
    known_tokens_strong: dict[str, dict],
    known_ngrams: dict[tuple[str, ...], dict],
    known_by_head_lemma: dict[str, list[dict]],
    lemma_map: dict[str, str],
    *,
    note_type: str = "word",
    translations: list[dict] | None = None,
    audio_ref: str | None = None,
    require_no_audio_for_sentence_rule: bool = False,
    apply_new_rules: bool = True,
) -> tuple[str, str | None, dict]:
    """Returns (verdict, rule, evidence). verdict is "import" or "skip".
    `text` is the candidate's own normalized text (its full surface form,
    pre-signature) — D13 attestation compares surface sequences, not D3
    signatures, which remain in use only for merge (section 5) and for the
    evidence-enrichment flag rules below.

    `apply_new_rules` is review-queue-filters' decision-precedence switch
    (task 6.1/D4): the caller passes `False` for any signature_key that
    already carries an operator decision, so a newly-introduced rule here
    can never flip an already-decided candidate's verdict — the pre-
    existing D13 attestation rules above are unaffected either way, since
    this flag only gates the *new* rules (sentence/proper-noun/
    nationality/numeral)."""
    tokens = lexeme.surface_tokens(text)
    head = signature[0]

    if apply_new_rules and note_type == "word" and is_pure_numeral(text):
        return "skip", "numeral", {"text": text}

    if len(tokens) == 1:
        lemma = lemma_map.get(tokens[0], tokens[0])
        if lemma in known_tokens_strong:
            return "skip", "attested-token-strong", {"matched": known_tokens_strong[lemma]}
        if lemma in known_tokens:
            if lemma in denylist:
                return "import", "denylist-protected", {"denylisted_lemma": lemma}
            return "skip", "attested-token-weak", {"matched": known_tokens[lemma]}
        if apply_new_rules and note_type == "word":
            lexical_rule = classify_lexical_item(text, translations)
            if lexical_rule is not None:
                rule, evidence = lexical_rule
                return "skip", rule, evidence
    elif len(tokens) > 1 and tokens in known_ngrams:
        return "skip", "attested-ngram", {"matched": known_ngrams[tokens], "sequence": list(tokens)}

    same_head = known_by_head_lemma.get(head)
    if same_head and (signature[1] or signature[2]):
        return "import", "same-head-different-particle", {"cf_stock": same_head[0]}

    if len(tokens) > 1:
        all_known = all(
            (lemma_map.get(tok, tok) in known_tokens_strong) or (lemma_map.get(tok, tok) in known_tokens)
            for tok in tokens
        )
        if all_known:
            # Tasks 3.1-3.6 (design D1/D2): a sentence-shaped candidate
            # whose every word is known is skipped — compositional content
            # only (D1's hard lowercase guard lives inside
            # `normalize.is_sentence_shaped`, not here, so it can never be
            # bypassed by a scoring expression). No audio condition by
            # default (D2); `require_no_audio_for_sentence_rule` exists
            # only so the audit's sensitivity line (task 5.5) can report
            # the alternative.
            if apply_new_rules and normalize.is_sentence_shaped(text):
                audio_blocks_skip = require_no_audio_for_sentence_rule and bool(audio_ref)
                if not audio_blocks_skip:
                    return "skip", "fully-known-sentence", {"tokens": list(tokens)}
            return "import", "all-tokens-known-phrase-unknown", {"tokens": list(tokens)}

    return "import", None, {}


def build_known_set_context(conn: sqlite3.Connection) -> dict:
    """The known-set + lemma map `run()` needs, exposed so `audit.py` can
    recompute verdicts under different flags (decision-precedence
    disagreements, task 5.4; the audio-condition sensitivity line, task
    5.5) without duplicating this construction."""
    lemma_map = key_stage.build_combined_lemma_map(conn)
    cards = stock.load_stock_cards()
    lexicon = stock.build_norwegian_lexicon(conn)
    known_lines = stock.classify_known_lines(cards, lexicon, lemma_map)
    return {
        "lemma_map": lemma_map,
        "known_tokens": stock.build_known_tokens(known_lines, lemma_map),
        "known_tokens_strong": stock.build_known_tokens_strong(known_lines, lemma_map),
        "known_ngrams": stock.build_known_ngrams(known_lines),
        "known_by_head_lemma": stock.build_known_signatures(known_lines, lemma_map),
        "denylist": load_denylist(),
    }


def rows_for_judging(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.signature_key, s.head_lemma, s.particles_json, s.reflexive, s.complements_json,
               n.note_type, n.text, n.translations_json, n.audio_ref
        FROM signature s
        JOIN normalized n ON n.id = s.normalized_id
        """
    ).fetchall()


def row_signature(row: sqlite3.Row) -> tuple:
    return (
        row["head_lemma"],
        tuple(json.loads(row["particles_json"])),
        bool(row["reflexive"]),
        tuple(json.loads(row["complements_json"])),
    )


def run(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    import store

    rows = rows_for_judging(conn)
    count_in = len(rows)

    context = build_known_set_context(conn)
    lemma_map = context["lemma_map"]
    known_tokens = context["known_tokens"]
    known_tokens_strong = context["known_tokens_strong"]
    known_ngrams = context["known_ngrams"]
    known_by_head_lemma = context["known_by_head_lemma"]
    denylist = context["denylist"]

    # Task 6.1/6.2 (design D4): a signature already carrying an operator
    # decision is exempt from the *new* rules this change adds — an
    # explicit accept/reject outranks a later auto-skip. The pre-existing
    # D13 attestation rules are unaffected either way (`apply_new_rules`
    # only gates sentence/proper-noun/nationality/numeral).
    decided_signature_keys = {row["signature_key"] for row in conn.execute("SELECT signature_key FROM decision")}

    verdicts = []
    skipped_for_review = []
    seen_signature_keys = set()
    for row in rows:
        signature = row_signature(row)
        verdict, rule, evidence = judge_one(
            row["text"],
            signature,
            denylist,
            known_tokens,
            known_tokens_strong,
            known_ngrams,
            known_by_head_lemma,
            lemma_map,
            note_type=row["note_type"],
            translations=json.loads(row["translations_json"]),
            audio_ref=row["audio_ref"],
            apply_new_rules=row["signature_key"] not in decided_signature_keys,
        )
        verdicts.append((row["signature_key"], verdict, rule, evidence))
        if verdict == "skip" and row["signature_key"] not in seen_signature_keys:
            seen_signature_keys.add(row["signature_key"])
            skipped_for_review.append({"signature_key": row["signature_key"], "signature": signature, "evidence": evidence})

    store.replace_stage_table(conn, "judge")
    for signature_key, verdict, rule, evidence in verdicts:
        conn.execute(
            "INSERT INTO verdict (run_id, signature_key, verdict, rule, evidence_json) VALUES (?, ?, ?, ?, ?)",
            (run_id, signature_key, verdict, rule, json.dumps(evidence, ensure_ascii=False)),
        )
    conn.commit()

    SKIPPED_REVIEW_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SKIPPED_REVIEW_LOG_PATH, "w", encoding="utf-8") as f:
        for entry in skipped_for_review:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    count_skipped = sum(1 for _, v, _, _ in verdicts if v == "skip")
    count_import = count_in - count_skipped
    print(
        f"judge: {count_skipped} auto-skip ({count_skipped / count_in:.1%}), {count_import} import; "
        f"skipped set dumped to {SKIPPED_REVIEW_LOG_PATH} for spot-check (task 4.8/4b.14)"
    )

    count_out = len(verdicts)
    return count_in, count_out, 0
