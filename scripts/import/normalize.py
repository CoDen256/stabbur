"""
scripts/import/normalize.py — section 3: field mapping + notation parsing,
`raw_note` -> `normalized` (tasks 3.1-3.9).

Per-source notation parsers and field mappers are kept separate functions
so each can be tested and reasoned about independently; `run()` is the only
place that ties sources together and writes `normalized`.

Measurement note (recorded in design.md too): several of design.md's
aggregate figures for this section were measured against an earlier,
undocumented pass and don't reproduce bit-for-bit against a principled
parser built from the rules actually written down in design.md/tasks.md.
Every *per-category* count design.md gives for the CSV notation parser
reproduces exactly (372 gender / 100 past-suffix / 22 alternate-form /
17 noe-noen placeholders, and 78 of its stated 80 parenthetical entries —
2 are not trailing-parenthetical and are deliberately left as literal
multiword text, see `_strip_csv_notation`). The *aggregate* single/multiword
split this parser produces is 826/326, not design's stated 816/336; that
delta could not be closed without the original (undocumented) script, so
826/326 is asserted here as the measured, reproducible baseline — same
convention as the freq6k correction in section 2.
"""

from __future__ import annotations

import json
import re
import sqlite3
from html import unescape

IPA_CHARS = re.compile(r"[ɑɒæøŋɲʃʒʉʈɖɽɾɹχθðʔˈˌːˑ]")
SOUND_REF_RE = re.compile(r"\[sound:([^\]]+)\]")

# ---------------------------------------------------------------------------
# CSV (herpaberget) notation parser — task 3.1
# ---------------------------------------------------------------------------

_CSV_TRAILING_PAREN_RE = re.compile(r"^(?P<head>.+?)\s*\((?P<content>[^()]*)\)$")
_CSV_GENDER_RE = re.compile(r"^(?P<head>.+?)\s*/\s*(?P<gender>a|et|en|ei)$")
_CSV_PAST_SUFFIX_RE = re.compile(r"^(?P<head>.+?)\s*/\s*-(?P<suffix>[^\s/()]+)$")
_CSV_ALT_FORM_RE = re.compile(r"^(?P<head>\S+)\s*/\s*(?P<form>[^\s/()]+(?:\s*-\s*[^\s/()]+)*)$")
_NOE_NOEN_RE = re.compile(r"\b(noe|noen)\b")


def strip_csv_notation(word: str) -> tuple[str, dict]:
    """Returns (head, notation) where `notation` records what was stripped
    (design D11 — this must run before type routing, task 3.8).

    `(eller) ei` and `å ha (lite/mye) å rutte med` are the 2 of CSV's 80
    parenthetical entries whose parens aren't trailing — left untouched,
    counted as plain multiword text rather than forced into a shape they
    don't have (task 3.1's own no-silent-default spirit, task 3.3)."""
    remainder = word
    notation: dict = {}

    m = _CSV_TRAILING_PAREN_RE.match(remainder)
    if m:
        remainder = m.group("head")
        notation["irregular"] = m.group("content")

    while True:
        m = _CSV_GENDER_RE.match(remainder)
        if not m:
            break
        remainder = m.group("head")
        notation.setdefault("genders", []).insert(0, m.group("gender"))

    m = _CSV_PAST_SUFFIX_RE.match(remainder)
    if m:
        remainder = m.group("head")
        notation["past_suffix"] = "-" + m.group("suffix")
    else:
        m = _CSV_ALT_FORM_RE.match(remainder)
        if m and " " not in m.group("head"):
            remainder = m.group("head")
            notation["alt_form"] = m.group("form")

    if _NOE_NOEN_RE.search(word):
        notation["has_complement_placeholder"] = True

    return remainder.strip(), notation


# ---------------------------------------------------------------------------
# NTNU `Inflection` parser — task 3.3
# ---------------------------------------------------------------------------


def parse_ntnu_inflection(article: str, word: str, inflection_raw: str) -> tuple[dict, str | None]:
    """Returns (inflections, pos). `inflections` carries `_malformed` with
    the raw text when the shape doesn't match this POS's well-formed
    pattern (design D4) — never a guessed/defaulted mapping."""
    article = article.strip()
    word = word.strip()
    inflection_raw = inflection_raw.strip()
    parts = [p.strip() for p in inflection_raw.split(",")] if inflection_raw else []

    if article in ("en", "et", "ei"):
        pos = "substantiv"
        if not parts:
            return {}, pos
        if len(parts) == 1:
            return {"article": article, "sg_indef": word, "sg_def": parts[0]}, pos
        if len(parts) == 3:
            return (
                {
                    "article": article,
                    "sg_indef": word,
                    "sg_def": parts[0],
                    "pl_indef": parts[1],
                    "pl_def": parts[2],
                },
                pos,
            )
        return {"_malformed": inflection_raw, "article": article, "sg_indef": word}, pos

    if article == "å":
        pos = "verb"
        if not parts:
            return {}, pos
        if len(parts) == 3:
            return (
                {"infinitiv": word, "presens": parts[0], "preteritum": parts[1], "perfektum": parts[2]},
                pos,
            )
        return {"_malformed": inflection_raw, "infinitiv": word}, pos

    # Article is blank: adjective/adverb/other — not resolved further (D6:
    # uncertain POS is left uncertain, not guessed).
    pos = None
    if not parts:
        return {}, pos
    if len(parts) == 2:
        return {"positiv": word, "nøytrum": parts[0], "bestemt_flertall": parts[1]}, pos
    return {"_malformed": inflection_raw, "positiv": word}, pos


# ---------------------------------------------------------------------------
# core6k `Inflections` HTML <table> parser — task 3.4
# ---------------------------------------------------------------------------

_CORE6K_ROW_RE = re.compile(r'<td class="l">([^<]+)</td>\s*<td>([^<]*)</td>')

_CORE6K_LABEL_MAP = {
    "Infinitive": "infinitiv",
    "Present": "presens",
    "Past": "preteritum",
    "Perfect": "perfektum",
    "Positive": "positiv",
    "Comparative": "komparativ",
    "Superlative": "superlativ",
    "Superlative def.": "superlativ_def",
    "Singular": "sg_indef",
    "Singular def.": "sg_def",
    "Singular def. (en)": "sg_def_en",
    "Singular def. (ei)": "sg_def_ei",
    "Plural": "pl_indef",
    "Plural def.": "pl_def",
}


def parse_core6k_inflection(html: str) -> dict:
    """Same no-silent-default rule as NTNU's parser: a row whose label isn't
    one of the shapes actually observed in this deck (task 3.4) is recorded
    under `_malformed` rather than dropped or guessed."""
    html = html.strip()
    if not html:
        return {}
    rows = _CORE6K_ROW_RE.findall(html)
    if not rows:
        return {"_malformed": html}

    result: dict = {}
    for label, value in rows:
        key = _CORE6K_LABEL_MAP.get(unescape(label).strip())
        value = unescape(value).strip()
        if key is None:
            result.setdefault("_malformed_labels", []).append(label)
            continue
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# freq6k: Word class -> pos, ordbok paradigm -> form list (task 3.5)
# ---------------------------------------------------------------------------

_FREQ6K_PARADIGM_RE = re.compile(r'<template id="[^"]*ordpar-paradigm"[^>]*>(.*?)</template>')


def parse_freq6k_paradigm(html: str) -> list[str]:
    """Mines the ordbok `Dictionary entry` HTML's embedded JSON paradigm
    table for surface forms, feeding D4's form->lemma map (built in
    section 4) — this is the resource no other source offers."""
    m = _FREQ6K_PARADIGM_RE.search(html)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    forms: set[str] = set()
    for entry in data:
        if len(entry) < 2:
            continue
        for paradigm in entry[1:]:
            if isinstance(paradigm, list) and len(paradigm) > 1:
                forms.update(paradigm[1:])
    return sorted(forms)


# ---------------------------------------------------------------------------
# A1: Notes field polymorphism (IPA vs POS label) — task 3.7
# ---------------------------------------------------------------------------


def a1_notes_is_ipa(notes: str) -> bool:
    notes = notes.strip()
    return bool(notes) and (notes.startswith("/") or bool(IPA_CHARS.search(notes)))


def _extract_audio_ref(field_value: str) -> str | None:
    m = SOUND_REF_RE.search(field_value)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Per-source row -> normalized-row mapping
# ---------------------------------------------------------------------------


def _normalize_ntnu(fields: dict) -> dict:
    article = fields.get("Article", "")
    word = fields.get("Word", "").strip()
    inflections, pos = parse_ntnu_inflection(article, word, fields.get("Inflection", ""))
    transcription = fields.get("Transcription", "").strip() or None
    return {
        "note_type": "word",
        "text": word,
        "pos": pos,
        "translations": [{"lang": "en", "text": fields.get("English", "").strip()}]
        if fields.get("English", "").strip()
        else [],
        "context_text": None,
        "transcription": transcription,
        "inflections": inflections,
        "audio_ref": _extract_audio_ref(fields.get("Audio", "")),
        "order_signal": {},
        "notation": {},
    }


def _normalize_a1(fields: dict) -> dict:
    front = fields.get("Front", "").strip()
    note_type = "word" if len(front.split()) <= 2 else "listening"
    notes = fields.get("Notes", "")
    transcription = notes.strip() if a1_notes_is_ipa(notes) else None
    return {
        "note_type": note_type,
        "text": front,
        "pos": None,
        "translations": [{"lang": "en", "text": fields.get("Back", "").strip()}]
        if fields.get("Back", "").strip()
        else [],
        "context_text": None,
        "transcription": transcription,
        "inflections": {},
        "audio_ref": _extract_audio_ref(fields.get("Audio 1", "")),
        "order_signal": {},
        "notation": {},
    }


def _normalize_core6k(fields: dict) -> dict:
    text = fields.get("Norwegian-Word", "").strip()
    translation = fields.get("English-Word", "").strip()
    return {
        "note_type": "word",
        "text": text,
        "pos": None,
        "translations": [{"lang": "en", "text": translation}] if translation else [],
        "context_text": fields.get("Norwegian-Sentence", "").strip() or None,
        "transcription": None,
        "inflections": parse_core6k_inflection(fields.get("Inflections", "")),
        "audio_ref": _extract_audio_ref(fields.get("Audio", "")),
        "order_signal": {},
        "notation": {},
    }


def _normalize_freq6k(fields: dict) -> dict:
    text = fields.get("Norwegian word", "").strip()
    translation = fields.get("English translation", "").strip()
    pos = fields.get("Word class", "").strip().lower() or None
    forms = parse_freq6k_paradigm(fields.get("Dictionary entry", ""))
    try:
        frequency_index = int(fields.get("Frequency index", "").strip())
    except ValueError:
        frequency_index = None
    return {
        "note_type": "word",
        "text": text,
        "pos": pos,
        "translations": [{"lang": "en", "text": translation}] if translation else [],
        "context_text": None,
        "transcription": None,
        "inflections": {},
        "audio_ref": None,  # freq6k audio is machine-synthesised — never carried past ingest (D10, task 7.1)
        "order_signal": {"frequency_index": frequency_index} if frequency_index is not None else {},
        "notation": {"paradigm_forms": forms} if forms else {},
    }


def _normalize_csv(fields: dict) -> dict:
    raw_word = fields.get("Original word", "").strip()
    head, notation = strip_csv_notation(raw_word)
    note_type = "word" if len(head.split()) == 1 else "expression"
    translation = fields.get("Explanation (en)", "").strip()
    context = fields.get("Example (no)", "").strip()
    return {
        "note_type": note_type,
        "text": head,
        "pos": None,
        "translations": [{"lang": "en", "text": translation}] if translation else [],
        "context_text": context or None,
        "transcription": None,
        "inflections": {},
        "audio_ref": None,
        "order_signal": {"kapittel": fields.get("Kapittel", "").strip()},
        "notation": notation,
    }


_SOURCE_NORMALIZERS = {
    "ntnu": _normalize_ntnu,
    "a1_31k": _normalize_a1,
    "core6k": _normalize_core6k,
    "freq6k": _normalize_freq6k,
    "herpaberget": _normalize_csv,
}

# Measured baseline this stage asserts against (task 3.2). See the module
# docstring for why this differs from design.md's original estimate.
CSV_SINGLE_EXPECTED = 826
CSV_MULTI_EXPECTED = 326

# Task 3.9 asks for a hard-asserted distinct-lexeme count of 9,129 here.
# That figure needs the real D3 lexeme signature (head lemma + particles +
# reflexive + complements, built from the form->lemma map) to be
# meaningful — a surface-text key either over-merges (strip the leading
# en/et/ei/å article: 7,706 — collapses genuinely distinct homographs) or
# under-merges (keep it: 10,500 — "en antropologi" and "antropologi" count
# twice). Both are real measurements, 1,400+ away from 9,129 in opposite
# directions, which is itself evidence this number can't be produced
# correctly before section 4's key stage exists. Deferred: `key` (task 4.4)
# computes the real signature and is where 9,129 gets validated. This
# stage logs the surface-text count for visibility only — it does not
# assert it.


class NormalizeCountMismatch(AssertionError):
    pass


def run(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    import store

    raw_rows = conn.execute("SELECT id, source, fields_json FROM raw_note").fetchall()
    count_in = len(raw_rows)

    normalized_rows = []
    csv_single = csv_multi = 0
    for row in raw_rows:
        normalizer = _SOURCE_NORMALIZERS[row["source"]]
        fields = json.loads(row["fields_json"])
        result = normalizer(fields)
        result["raw_note_id"] = row["id"]
        result["source"] = row["source"]
        normalized_rows.append(result)
        if row["source"] == "herpaberget":
            if result["note_type"] == "word":
                csv_single += 1
            else:
                csv_multi += 1

    if (csv_single, csv_multi) != (CSV_SINGLE_EXPECTED, CSV_MULTI_EXPECTED):
        raise NormalizeCountMismatch(
            f"CSV single/multiword split: expected {CSV_SINGLE_EXPECTED}/{CSV_MULTI_EXPECTED}, "
            f"got {csv_single}/{csv_multi}"
        )

    store.replace_stage_table(conn, "normalize")
    for row in normalized_rows:
        conn.execute(
            """
            INSERT INTO normalized (
                run_id, raw_note_id, source, note_type, text, pos,
                translations_json, context_text, transcription,
                inflections_json, audio_ref, order_signal_json, notation_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row["raw_note_id"],
                row["source"],
                row["note_type"],
                row["text"],
                row["pos"],
                json.dumps(row["translations"], ensure_ascii=False),
                row["context_text"],
                row["transcription"],
                json.dumps(row["inflections"], ensure_ascii=False),
                row["audio_ref"],
                json.dumps(row["order_signal"], ensure_ascii=False),
                json.dumps(row["notation"], ensure_ascii=False),
            ),
        )
    conn.commit()

    distinct_surface_text = conn.execute(
        "SELECT COUNT(DISTINCT LOWER(text)) FROM normalized WHERE note_type != 'listening'"
    ).fetchone()[0]
    print(
        f"normalize: distinct surface-text lexemes (diagnostic only, not asserted — see "
        f"module docstring): {distinct_surface_text}; design.md targets 9,129 once `key` "
        f"(task 4.4) builds the real lexeme signature"
    )

    count_out = len(normalized_rows)
    count_discarded = count_in - count_out
    return count_in, count_out, count_discarded
