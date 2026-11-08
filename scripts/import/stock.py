"""
scripts/import/stock.py — the stock known-set extractor, rewritten under
design D13 (tasks 4b.1-4b.6; supersedes the D5 field-role extractor this
module used to implement — see design.md's D5/D13 sections and tasks.md
section 4 vs 4b).

Parses `~/mjolnir/index.android.bundle.exploded/2113.js` (a React Native
module: `__d(function(...) { t.exports = [ {DECK_ID, ID, N, E, D, X, A}, ...
] }, ...)`), which is JS-object-literal shaped, not strict JSON (bare keys,
backslash-x hex string escapes) — `_load_raw_entries` below does the
minimal transform needed (quote the fixed key set, backslash-x-HH ->
backslash-u-00HH) and then uses the stdlib `json` module; no JS engine or
third-party parser.

Path correction (recorded like the others in design.md): the stock bundle
is not at design.md's literal `~/mjolnir/...` path on this operator's
machine — it's at `~/dev/mjolnir/index.android.bundle.exploded/2113.js`.
Overridable via `STABBUR_IMPORT_STOCK_BUNDLE` for whoever runs this next.

**D13's extraction has no card-template classification, no deck exclusions,
and no field-role mapping (task 4b.1).** Every one of a card's free-text
fields (`N`, `E`, `X`, `D`) is scanned uniformly; `A` is a structural
one-letter flag (`"N"`/`"E"`/`"X"`), not content, and is not scanned.
Whether a line is Norwegian is decided purely by scoring it against a
lexicon built from the *import sources'* own text (`build_norwegian_lexicon`,
task 4b.2) — never by which field it came from or which deck it is in. This
is what removes the entire bug family recorded in design.md's section-4 and
section-5 correction notes (the `A`-field check, `_EXCLUDED_PROSE_DECKS`,
`_ALWAYS_MINE_E_DECKS`, the deny-list-before-match ordering): none of that
machinery exists any more.

The known-set is two things, built from every line stock-wide that scores
as Norwegian (`classify_known_lines`):

- `KNOWN_TOKENS` (task 4b.5) — every token of every Norwegian line, closed
  expansively over inflection (D13.3): if any attested form resolves to a
  lemma, every form of that lemma counts as known too. `KNOWN_TOKENS_STRONG`
  is the subset attested as a *standalone* one-token line — a dedicated
  card teaching exactly that word, not a word merely used somewhere inside
  a longer sentence. judge.py treats this subset as un-vetoable by the
  deny-list (D13.4); the rest is "weak" evidence the deny-list may block.
- `KNOWN_NGRAMS` (task 4b.6) — every contiguous word sequence of every
  Norwegian line, length 2 up to the line's own length, with no upper cap:
  the operator's own rule ("I know every combination that is still there")
  covers full sentences and every subset of them, not just short phrases.

**Measured limitation, found while tuning the D13.1 line classifier against
this bundle (task 4b.4), recorded here in this repo's usual
measure-and-document style rather than silently accepted:** the Norwegian
lexicon (`build_norwegian_lexicon`) is built only from the import sources'
own *base* word list (~8,057 tokens) — it has no general inflectional
coverage, so a line carrying several inflected or rare forms (names,
superlatives, past tenses absent from that lexicon) can score as
insufficiently Norwegian even when a human would read it as an ordinary
Norwegian sentence. Measured consequence: `man` (the Norwegian indefinite
pronoun, not just the English homograph) genuinely is attested 8 times in
real stock sentences in this bundle, one over the ≤7 ceiling design.md
records; `den` has no *standalone* one-token card in this bundle at all
(only sentence-embedded, "weak" attestation) despite design's assumption
that it is one of the 11 "taught directly" words — both are consequences of
this specific bundle's content and this classifier's precision, not bugs in
the attestation rule itself, and are accepted the same way this change's
other measured-not-estimated figures are (design.md's D13 section).

Two of the deny-list's entries — `and` and `a` — have a *literal* standalone
one-token line in this bundle (`Z02066`/`A05006`'s `E` field is exactly
"and"; `A10002`'s `E` field is exactly "a") that is verified, by reading the
cards directly, to be the English half of a translation pair (`og` -> "and",
and an English letter-naming answer), not genuine Norwegian attestation of
"and" (duck) or the indefinite article. A purely lexical, corpus-only
classifier cannot distinguish a true homograph attestation from this one by
content alone — the string is identical either way — so these two are
excluded from `KNOWN_TOKENS_STRONG` by name, found by the same kind of
direct inspection task 4.8 and 4b.12 call for, not inferred automatically.
"""

from __future__ import annotations

import html
import json
import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import lexeme

DEFAULT_STOCK_BUNDLE_PATH = Path.home() / "mjolnir" / "index.android.bundle.exploded" / "2113.js"


def stock_bundle_path() -> Path:
    override = os.environ.get("STABBUR_IMPORT_STOCK_BUNDLE")
    return Path(override) if override else DEFAULT_STOCK_BUNDLE_PATH


_BARE_KEY_RE = re.compile(r"(?<=[{,\s])(DECK_ID|ID|N|E|D|X|A)(?=\s*:)")
_HEX_ESCAPE_RE = re.compile(r"\\x([0-9A-Fa-f]{2})")

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)

EXCLUDED_DECK_PREFIX = "C2"
C03_DECK_ID = "C03"

# Every free-text field on a card — D13.1 scans all of them uniformly, no
# field singled out as "the" Norwegian field (task 4b.1). `A` is a one-letter
# structural flag, not content, and is deliberately absent from this list.
TEXT_FIELDS = ("N", "E", "X", "D")

# A fixed, hand-maintained list — not an attempt at general English
# detection, just the vocabulary observed recurring in this bundle's
# instructional/explanatory prose, tuned against the measured leakage
# ceiling in design D13.2 (`the` 0, `is` <=2, `that` 0, `and` <=4, `man`
# <=7, `a` <=39 — see task 4b.4 and this module's docstring for the two
# measured deviations).
ENGLISH_STOPWORDS = frozenset(
    {
        "the", "is", "are", "was", "were", "be", "been", "being", "a", "an", "and", "or", "but", "not", "no",
        "to", "of", "in", "on", "at", "by", "for", "with", "as", "from", "this", "these", "those",
        "it", "its", "he", "she", "they", "we", "you", "your", "his", "her", "their", "our", "i", "my", "me",
        "what", "how", "why", "when", "where", "who", "which", "do", "does", "did", "will", "would", "should",
        "can", "could", "may", "might", "must", "have", "has", "had", "man", "men", "provide", "list", "identify",
        "translate", "turn", "name", "give", "complete", "fill", "choose", "select", "write", "form", "conjugate",
        "read", "say", "describe", "explain", "state", "compare", "comparative", "superlative", "imperative",
        "adjective", "adverb", "noun", "verb", "pronoun", "sentence", "word", "meaning", "example", "examples",
        "following", "above", "below", "instead", "rather", "same", "different", "own", "each", "such", "way",
        "ways", "refers", "things", "thing", "people", "person", "note", "notes", "also", "only", "more", "most",
        "than", "then", "now", "here", "there", "if", "so", "because", "about", "into", "over", "under", "between",
        "all", "some", "any", "every", "other", "another", "many", "much", "few", "several", "both", "either",
        "neither", "like", "see", "shows", "indicates", "used", "use", "uses", "meanings", "sense", "case", "cases",
        "correct", "number", "plural", "singular", "tense", "forms",
    }
)

# Measured by direct inspection (task 4b.4/4b.12): these two lemmas have a
# standalone one-token line in this bundle, but it's the English half of a
# translation pair, not genuine Norwegian attestation — see module
# docstring. Excluded from "strong" (dedicated-card) evidence by name.
_VERIFIED_FALSE_STRONG = frozenset({"and", "a"})

LEX_SHARE_THRESHOLD = 0.6
STOPWORD_SHARE_THRESHOLD = 0.15


def _load_raw_entries(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    start = text.index("t.exports = [")
    start_bracket = text.index("[", start)
    depth = 0
    end = None
    for i in range(start_bracket, len(text)):
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        raise ValueError(f"{path}: could not find matching ']' for the exports array")

    array_text = text[start_bracket : end + 1]
    array_text = _BARE_KEY_RE.sub(r'"\1"', array_text)
    array_text = _HEX_ESCAPE_RE.sub(lambda m: "\\u00" + m.group(1), array_text)
    return json.loads(array_text)


def load_stock_cards(path: Path | None = None) -> list[dict]:
    """All non-`C2*` cards (design: 2,801 raw entries, 11 in `C2*`
    decks — stabbur's own P4 seed — leaving 2,790; design.md's stated
    13/2,788 corrected here, see design.md's implementation-correction
    note). This is the one deck exclusion D13 keeps (task 4b.1) — it isn't
    a card-structure assumption about stock's own content, it's excluding
    content that *isn't* stock at all."""
    entries = _load_raw_entries(path or stock_bundle_path())
    return [e for e in entries if not e["DECK_ID"].startswith(EXCLUDED_DECK_PREFIX)]


def bootstrap_c03_lemma_map(cards: list[dict]) -> dict[str, str]:
    """C03's own cards give a full conjugation set per entry — e.g. `å late
    til / later / lot / har latt / lat!` — bootstrapping form->lemma for
    exactly these forms before they're needed to build C03's own
    signatures (design D4's last listed lemma-data source). This is D4
    lemma resolution, retained unchanged under D13 (which only supersedes
    D5's *known-set extraction*, not D4's lemma map, per tasks.md's section
    4b preamble)."""
    form_to_lemma: dict[str, str] = {}
    for card in cards:
        if card["DECK_ID"] != C03_DECK_ID:
            continue
        field_html = card["E"]
        without_tags = TAG_RE.sub(lambda m: "<br>" if m.group(0).lower().startswith("<br") else " ", field_html)
        without_tags = without_tags.replace("(", " ").replace(")", " ")
        lines = [WHITESPACE_RE.sub(" ", ln).strip() for ln in BR_RE.split(without_tags)]
        lines = [ln for ln in lines if ln]
        if not lines:
            continue
        head_tokens = lexeme._INFINITIVE_MARKER_RE.sub("", lines[0]).split()
        if not head_tokens:
            continue
        lemma = lexeme._clean_token(head_tokens[0])
        for form_line in lines[1:]:
            for tok in form_line.split():
                form_to_lemma[lexeme._clean_token(tok)] = lemma
    return form_to_lemma


def _split_lines(field_html: str) -> list[str]:
    """`<br>`-separated lines only (task 4b.3) — inline tags (`<b>`,
    `<span>`, ...) are *removed*, never split on, and parenthesis
    *characters* are removed while their contents are kept as ordinary
    tokens (this repo's own section-4 correction: a parenthetical is
    sometimes a word's own defining complement, e.g. "å late (som om)" or
    "å bekymre (seg for)", not an aside — see design.md). Splitting on
    inline tags instead of removing them was measured to fragment English
    prose into 1-2 word pieces that then falsely score as Norwegian (task
    4b.3's "and" scores 100% Norwegian" hazard)."""
    lines = []
    for part in BR_RE.split(field_html):
        text = TAG_RE.sub("", part)
        text = html.unescape(text)
        text = text.replace("(", " ").replace(")", " ")
        text = WHITESPACE_RE.sub(" ", text).strip()
        if text:
            lines.append(text)
    return lines


def _tokenize(line: str) -> tuple[str, ...]:
    return tuple(lexeme._clean_token(tok) for tok in line.split() if lexeme._clean_token(tok))


def iter_card_lines(cards: list[dict]) -> list[tuple[tuple[str, ...], dict]]:
    """Every `<br>`-delimited, tokenized line from every free-text field of
    every card, regardless of field or deck (task 4b.1). Returns
    (tokens, evidence) pairs; language classification happens separately
    in `classify_known_lines` so this function stays a pure, inspectable
    extraction step."""
    results = []
    for card in cards:
        for field_name in TEXT_FIELDS:
            field_html = card.get(field_name) or ""
            for line in _split_lines(field_html):
                tokens = _tokenize(line)
                if tokens:
                    results.append((tokens, {"deck_id": card["DECK_ID"], "card_id": card["ID"], "field": field_name, "text": line}))
    return results


def build_norwegian_lexicon(conn: sqlite3.Connection) -> frozenset[str]:
    """The Norwegian lexicon used to score stock's lines (D13.1, task
    4b.2) — built from the *import sources'* own `normalized.text`
    (~8,026 tokens per design.md; ~8,057 measured here), never from stock.
    This one-way dependency (import sources -> lexicon -> stock scoring) is
    what makes the known-set extraction independent of stock's own card
    structure."""
    rows = conn.execute("SELECT text FROM normalized").fetchall()
    tokens = set()
    for row in rows:
        for tok in (row["text"] or "").split():
            cleaned = lexeme._clean_token(tok)
            if cleaned:
                tokens.add(cleaned)
    return frozenset(tokens)


def _is_norwegian_line(tokens: tuple[str, ...], lexicon: frozenset[str], lemma_map: dict[str, str]) -> bool:
    """D13.1: Norwegian when lexicon share is high and English-stopword
    share is low; short lines require unanimity (task 4b.4). A token
    counts toward the lexicon if either its surface form or its D4-mapped
    lemma is in the import-source lexicon — plain surface lookup alone
    under-recognises ordinary inflected forms the small (~8k-token)
    lexicon never sees verbatim (this module's docstring records the
    measured cost of this gap: `man`/`den`)."""
    if not tokens:
        return False
    n = len(tokens)

    def in_lexicon(tok: str) -> bool:
        return tok in lexicon or lemma_map.get(tok) in lexicon

    lex_hits = sum(1 for t in tokens if in_lexicon(t))
    stop_hits = sum(1 for t in tokens if t in ENGLISH_STOPWORDS)

    if n == 1:
        # A solitary token's own English-stopword status is irrelevant: if
        # it's independently attested in the Norwegian lexicon, a
        # dedicated one-word card teaching it is exactly what "taught
        # directly" (task 4b.8) means, homograph or not.
        return lex_hits == 1
    if n == 2:
        return stop_hits == 0 and lex_hits == n
    if lex_hits == n:
        return True
    return (lex_hits / n) >= LEX_SHARE_THRESHOLD and (stop_hits / n) <= STOPWORD_SHARE_THRESHOLD


def classify_known_lines(
    cards: list[dict], lexicon: frozenset[str], lemma_map: dict[str, str]
) -> list[tuple[tuple[str, ...], dict]]:
    """Every stock line that scores as Norwegian (D13.1). No deck or field
    is excluded (task 4b.1) — classification is purely per-line content."""
    return [
        (tokens, evidence)
        for tokens, evidence in iter_card_lines(cards)
        if _is_norwegian_line(tokens, lexicon, lemma_map)
    ]


def _inflection_reverse_map(lemma_map: dict[str, str]) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for form, lemma in lemma_map.items():
        reverse[lemma].add(form)
    return reverse


def build_known_tokens(
    known_lines: list[tuple[tuple[str, ...], dict]], lemma_map: dict[str, str]
) -> dict[str, dict]:
    """KNOWN_TOKENS (task 4b.5): every token of every Norwegian line,
    closed expansively over inflection (D13.3) — if any attested form
    resolves to a lemma, every form of that lemma is known too, inverting
    how the D4 form->lemma map narrowed matching for the old D3 signature
    comparison. Returns token/lemma -> evidence (first match wins)."""
    known: dict[str, dict] = {}
    attested_lemmas: set[str] = set()
    for tokens, evidence in known_lines:
        for tok in tokens:
            known.setdefault(tok, evidence)
            lemma = lemma_map.get(tok, tok)
            attested_lemmas.add(lemma)
            known.setdefault(lemma, evidence)

    reverse = _inflection_reverse_map(lemma_map)
    for lemma in attested_lemmas:
        for form in reverse.get(lemma, ()):
            known.setdefault(form, {"via_inflection_closure_of": lemma})
    return known


def build_known_tokens_strong(
    known_lines: list[tuple[tuple[str, ...], dict]], lemma_map: dict[str, str]
) -> dict[str, dict]:
    """The subset of KNOWN_TOKENS attested as a *standalone* one-token
    line — a dedicated card teaching exactly that word (task 4b.8's
    "taught directly"), not merely used somewhere inside a longer
    sentence. judge.py's deny-list check (D13.4) only vets the remainder;
    this subset is never vetoable. `_VERIFIED_FALSE_STRONG` excludes two
    lemmas found, by direct inspection, to be false positives in this
    bundle (see module docstring)."""
    strong_lines = [(tokens, evidence) for tokens, evidence in known_lines if len(tokens) == 1]
    strong = build_known_tokens(strong_lines, lemma_map)
    for lemma in _VERIFIED_FALSE_STRONG:
        strong.pop(lemma, None)
    return strong


def build_known_ngrams(known_lines: list[tuple[tuple[str, ...], dict]]) -> dict[tuple[str, ...], dict]:
    """KNOWN_NGRAMS (task 4b.6): every contiguous word sequence of every
    Norwegian line, length 2 up to the line's own length — no upper cap
    (D13.2). Stock's Norwegian text is small enough (a few thousand lines)
    that this is cheap even unbounded."""
    ngrams: dict[tuple[str, ...], dict] = {}
    for tokens, evidence in known_lines:
        n = len(tokens)
        for i in range(n):
            for j in range(i + 2, n + 1):
                ngrams.setdefault(tokens[i:j], evidence)
    return ngrams


def build_known_signatures(
    known_lines: list[tuple[tuple[str, ...], dict]], lemma_map: dict[str, str]
) -> dict[str, list[dict]]:
    """by_head_lemma: every known D3 signature sharing a head, for the
    same-head-different-particle flag rule (task 4.6/4b.7's evidence
    enrichment — this is no longer used to decide skips, only to annotate
    an import with a 'cf. stock' reference)."""
    by_head_lemma: dict[str, list[dict]] = defaultdict(list)
    for tokens, evidence in known_lines:
        signature = lexeme.build_signature(" ".join(tokens), lemma_map)
        if signature is None:
            continue
        by_head_lemma[signature[0]].append({**evidence, "signature": signature})
    return dict(by_head_lemma)
