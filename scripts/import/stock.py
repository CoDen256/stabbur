"""
scripts/import/stock.py — the stock known-set extractor (tasks 4.1, 4.2).

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

**Extraction is by field-role content, per design D5's own description —
not by the card's `A` field (task 4.2, corrected; see design.md's section
4 implementation-correction note).** `A` turned out to denote something
about the card's own quiz-answer side, unrelated to which field holds
Norwegian — confirmed directly: `A=="N"` cards exist where `N` opens with
an English question (`B09`'s "What is the meaning of X when it's used as
an adverb?"), and `A=="E"` cards exist across a dozen decks (`B01`-`B12`,
`A07`, `A10`, `Z01`, ~785 cards total) where `N` opens with an English
instruction ("List the four forms for:", "Provide the comparative and
superlative forms of this adjective:", "Translate using the correct verb
tense:") and `E` holds the actual Norwegian answer — common, high-value
vocabulary (`trene`, `viktig`, `handle`, `hjelp`, `ball`, ...) that the
`A`-keyed extraction was silently excluding in its entirety.

Design D5's actual rule: "if `N` opens with an English instruction or
question, Norwegian lives in `E` and in `N`'s continuation lines;
otherwise `N` itself is Norwegian." Implemented as `_opens_with_english`
(a word-list check on `N`'s first line) driving which fields get mined —
`N` alone when it doesn't open with English (unchanged from the original
A=="N" cards), or both `E` in full and `N`'s own continuation lines when
it does. The continuation-lines half matters for a third shape (`B01`,
pronunciation drills): `N` carries the instruction *and* the real
Norwegian examples as continuation, while `E` is English phonetic
commentary, not Norwegian at all — mining only `E` there would get
nothing useful and mining only `N`'s first line would miss everything.

Within an extracted field, parenthetical asides (`(no comparative and
superlative)`, `(include the imperative)`) are stripped before
tokenizing by default — this is the one concretely-identified source of
English leakage into otherwise-Norwegian fields (e.g. "and" inside
"kvitt, kvitt, kvitt (no comparative and superlative)"). Deck `C03` is
a verified, narrow exception (task 4.2's own earlier correction): its
conjugation answers use a parenthetical as the verb's own defining
complement (`"å late (som om)"` = "to pretend", distinct from bare
`"late"`), not an aside, so stripping there would silently drop an
already-taught sense. This doesn't eliminate residual leakage in general
for every other deck (design D5's accepted risk) — the homograph deny-list
(task 4.3) is the actual safety net for whatever slips past it.
"""

from __future__ import annotations

import json
import os
import re
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
PAREN_RE = re.compile(r"\([^()]*\)")
WHITESPACE_RE = re.compile(r"\s+")

EXCLUDED_DECK_PREFIX = "C2"
C03_DECK_ID = "C03"

# Instructional/question openers observed across the bundle's exercise
# decks ("List the four forms for:", "Provide the comparative and
# superlative forms of this adjective:", "Translate using...", "Turn the
# following sentence...", "What is the meaning of...", "Read out,
# focusing on..."). A word-list check on N's first line, not a general
# English-language detector — matching design D5's own "if N opens with
# an English instruction or question" phrasing, which names specific
# recurring templates rather than prose detection in general.
_ENGLISH_OPENER_RE = re.compile(
    r"^(what|how|why|when|where|which|who|is|are|do|does|can|could|will|would|should|"
    r"provide|list|identify|translate|turn|name|give|complete|fill|choose|select|write|"
    r"form|conjugate|read|say|describe|explain|state|compare)\b",
    re.IGNORECASE,
)

# B10/B11: uniformly A=="E" (80/80, 115/115, verified), N is a bare
# English sentence to translate with no instructional opener at all —
# the instruction lives only in the deck's own description, not
# per-card, so no word-list check on N can catch it. A scoped exception,
# not a reversion to trusting `A` generally (design.md's section 4
# correction note explains why `A` is unreliable elsewhere).
_ALWAYS_MINE_E_DECKS = frozenset({"B10", "B11"})

# A03/A04/A06/C01: confirmed by direct content inspection to be grammar
# EXPLANATION decks (multi-sentence prose about genders/pronouns/tone
# rules), not vocabulary or inflection lists — design D5's own excluded
# category ("excluding answer and prose fields entirely"). These also
# open with an English question, so they'd otherwise be swept into the
# same "mine E" path as the genuine vocabulary-drill decks. The <=6-word
# segment filter in `extract_known_segments` catches most of their
# length, but a short English grammar-term fragment can still slip under
# it (e.g. C01's "comparative" as its own segment) — these 4 decks are
# tiny (35 cards total) and unambiguous enough to exclude wholesale
# rather than chase a general prose-vs-vocabulary classifier.
_EXCLUDED_PROSE_DECKS = frozenset({"A03", "A04", "A06", "C01"})


def _opens_with_english(field_html: str) -> bool:
    first_line_html = re.split(r"<br\s*/?>", field_html, maxsplit=1, flags=re.IGNORECASE)[0]
    first_line_text = TAG_RE.sub(" ", first_line_html).strip()
    return bool(_ENGLISH_OPENER_RE.match(first_line_text))


def _continuation(field_html: str) -> str:
    """Everything in `field_html` after its first `<br>`-separated line —
    where, on cards whose first line is an English instruction, the real
    Norwegian content sometimes sits directly in `N` itself (design D5's
    "and in N's continuation lines")."""
    parts = re.split(r"<br\s*/?>", field_html, maxsplit=1, flags=re.IGNORECASE)
    return parts[1] if len(parts) > 1 else ""


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
    note)."""
    entries = _load_raw_entries(path or stock_bundle_path())
    return [e for e in entries if not e["DECK_ID"].startswith(EXCLUDED_DECK_PREFIX)]


def strip_html(html: str) -> str:
    text = TAG_RE.sub(" ", html)
    text = PAREN_RE.sub(" ", text)  # strip parentheticals before tokenizing
    return WHITESPACE_RE.sub(" ", text).strip()


_PAREN_ACROSS_LINES_RE = re.compile(r"\([^()]*?\)", re.DOTALL)


def _segments(field_html: str, strip_parens: bool = True) -> list[str]:
    """`<br>`-separated lines, each further split on commas — each
    resulting segment is one known phrase/form, not the whole field.

    `strip_parens` distinguishes two genuinely different uses of
    parentheses across the sources this reads:

    - In a regular `A=="N"` vocabulary field, a parenthetical is a usage
      *aside* (`"(comparative and superlative are not in use)"`, deck
      B05) — not part of the word, safe to discard wholesale. Default
      True for this reason; done on the *whole field* before `<br>`
      splitting, not per line, since some asides span a `<br>` themselves
      (`"(comparative and superlative<br> are not in use)"`) and
      stripping per-line would leave the opening half dangling as a false
      "known" segment.
    - In C03's conjugation-answer field, a parenthetical directly after
      the infinitive is the verb's own defining complement, not an aside
      — `"å late (som om)"` (deck C03, card C03011) means "to pretend",
      distinct from bare `"late"` (C03002). Discarding it as an aside
      would silently drop a real, already-taught sense from the
      known-set — caught by spot-checking the skipped set for an item
      the operator already knew wasn't in it (task 4.8's whole point).
      Call with `strip_parens=False` here; parens are then just
      punctuation characters removed, keeping their contents as
      ordinary tokens."""
    without_tags = TAG_RE.sub(lambda m: "<br>" if m.group(0).lower().startswith("<br") else " ", field_html)
    if strip_parens:
        without_tags = _PAREN_ACROSS_LINES_RE.sub(" ", without_tags)
    else:
        without_tags = without_tags.replace("(", " ").replace(")", " ")
    lines = re.split(r"<br\s*/?>", without_tags, flags=re.IGNORECASE)
    segments = []
    for line in lines:
        clean = WHITESPACE_RE.sub(" ", line).strip()
        if not clean:
            continue
        for part in clean.split(","):
            part = part.strip()
            if part:
                segments.append(part)
    return segments


def bootstrap_c03_lemma_map(cards: list[dict]) -> dict[str, str]:
    """C03's own cards give a full conjugation set per entry — e.g. `å late
    til / later / lot / har latt / lat!` — bootstrapping form->lemma for
    exactly these forms before they're needed to build C03's own
    signatures (design D4's last listed lemma-data source)."""
    form_to_lemma: dict[str, str] = {}
    for card in cards:
        if card["DECK_ID"] != C03_DECK_ID:
            continue
        segments = _segments(card["E"], strip_parens=False)
        if not segments:
            continue
        head_line = segments[0]
        head_tokens = lexeme._INFINITIVE_MARKER_RE.sub("", head_line).split()
        if not head_tokens:
            continue
        lemma = lexeme._clean_token(head_tokens[0])
        for form in segments[1:]:
            for tok in form.split():
                form_to_lemma[lexeme._clean_token(tok)] = lemma
    return form_to_lemma


def extract_known_segments(cards: list[dict]) -> list[tuple[str, dict]]:
    """Returns (segment_text, evidence) pairs. `evidence` carries enough to
    build task 4.6's "cf. stock" references (deck/card id + the original
    field text).

    Field-role decided by `N`'s own content (design D5), not by the
    card's `A` field — see the module docstring's section 4 correction
    note for why `A` doesn't actually denote language location."""
    results = []
    for card in cards:
        if card["DECK_ID"] in _EXCLUDED_PROSE_DECKS:
            continue
        sources = []
        if _opens_with_english(card["N"]) or card["DECK_ID"] in _ALWAYS_MINE_E_DECKS:
            # Norwegian lives in E in full, and sometimes in N's own
            # continuation (pronunciation drills like B01, where E is
            # English phonetic commentary rather than Norwegian at all).
            strip_parens = card["DECK_ID"] != C03_DECK_ID
            sources.append(("E", card["E"], strip_parens))
            continuation = _continuation(card["N"])
            if continuation:
                sources.append(("N", continuation, True))
        else:
            sources.append(("N", card["N"], True))

        for field_name, field_html, strip_parens in sources:
            for segment in _segments(field_html, strip_parens=strip_parens):
                # Grammar-explanation decks (A06, C01, ...) also open with
                # an English question, but their answer is prose, not a
                # vocabulary/inflection list — design's own stated
                # validation measures known phrases at <=6 words, which
                # doubles as a clean filter: prose sentences ("Norwegian
                # can have a comparative form of adjectives.") run well
                # past that, short vocabulary/inflection segments never
                # do. Longer segments are dropped, not flagged — this is
                # about what counts as "known", not a candidate verdict.
                if len(segment.split()) > 6:
                    continue
                results.append(
                    (
                        segment,
                        {"deck_id": card["DECK_ID"], "card_id": card["ID"], "field": field_name, "text": segment},
                    )
                )
    return results


def build_known_signatures(
    cards: list[dict], lemma_map: dict[str, str]
) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """Returns (by_signature_key, by_head_lemma):
    - by_signature_key: exact-match lookup for auto-skip (task 4.5)
    - by_head_lemma: every known signature sharing a head, for the
      same-head-different-particle flag rule (task 4.6)
    """
    by_signature_key: dict[str, dict] = {}
    by_head_lemma: dict[str, list[dict]] = defaultdict(list)

    for segment, evidence in extract_known_segments(cards):
        signature = lexeme.build_signature(segment, lemma_map)
        if signature is None:
            continue
        key = lexeme.signature_key(signature)
        evidence = {**evidence, "signature": signature}
        by_signature_key.setdefault(key, evidence)
        by_head_lemma[signature[0]].append(evidence)

    return by_signature_key, dict(by_head_lemma)
