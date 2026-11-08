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

**Extraction is deliberately narrow (task 4.2, design D5's tightened
rule):** only `A == "N"` entries (where `N` itself is the vocabulary
headword/sentence — confirmed against real samples: `A=="N"` means N is
plain Norwegian, `A` in `("E","X")` means N is an English question and the
answer field is instructional prose) and deck `C03`'s tense-exercise
answers (named explicitly in design D4) are read. Every other field on
every other card — explanatory prose, grammar answers — is excluded
entirely, not merely down-weighted. HTML emphasis markup is not used as a
language signal (measured in design D5 to carry none).

Within an extracted field, parenthetical asides (`(no comparative and
superlative)`, `(include the imperative)`) are stripped before
tokenizing — these are the one concretely-identified source of English
leakage into otherwise-Norwegian fields (e.g. "and" inside "kvitt, kvitt,
kvitt (no comparative and superlative)"). This doesn't eliminate residual
leakage in general (design D5's accepted risk) — the homograph deny-list
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


def _segments(field_html: str) -> list[str]:
    """`<br>`-separated lines, each further split on commas — each
    resulting segment is one known phrase/form, not the whole field.

    Parenthetical asides are stripped on the *whole field* before `<br>`
    splitting, not per line — some of them span a `<br>` themselves (e.g.
    `"(comparative and superlative<br> are not in use)"`, deck B05), and
    stripping per-line would leave the opening half dangling as a false
    "known" segment."""
    without_tags_or_parens = TAG_RE.sub(lambda m: "<br>" if m.group(0).lower().startswith("<br") else " ", field_html)
    without_tags_or_parens = _PAREN_ACROSS_LINES_RE.sub(" ", without_tags_or_parens)
    lines = re.split(r"<br\s*/?>", without_tags_or_parens, flags=re.IGNORECASE)
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
        segments = _segments(card["E"])
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
    field text)."""
    results = []
    for card in cards:
        sources = []
        if card["A"] == "N":
            sources.append(("N", card["N"]))
        if card["DECK_ID"] == C03_DECK_ID:
            sources.append(("E", card["E"]))

        for field_name, field_html in sources:
            for segment in _segments(field_html):
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
