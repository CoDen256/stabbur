"""
scripts/import/merge.py — section 5: `normalized` (grouped by lexeme
signature) -> `candidate` (tasks 5.1-5.5, design D7/D8).

One candidate per D3 lexeme signature (task 5.1) — the signature keeps its
merge role under D13 even though D13 replaced its *skip* role (tasks.md's
section 4b preamble). Field-level priority is fixed and operator-set
(design D8):

    NTNU > A1 31k > core6k > freq6k > CSV

For every field, the highest-priority source with a non-empty value wins;
no averaging, concatenation, or voting (task 5.2). Every other non-empty
value supplied by a lower-priority source is retained on the candidate and
the candidate is flagged conflicted if it disagrees with the winner
(task 5.3) — a silent merge would hide exactly the information (two
sources glossing a word differently) that makes review fast.

Review ordering (task 5.5, design D7): freq6k's `Frequency index`, then a
`CEFR::*` Anki tag, then the CSV's chapter/section — in that order, with
candidates carrying no signal sorted last. **Measured note:** this bundle's
`core6k` deck carries no `CEFR::*` tags at all (only thematic/continent
tags on its `Country` model) — the CEFR tier of the ordering key is
implemented per design D7 but never actually discriminates against this
specific bundle's data; recorded here the same way this change records
other measured-not-assumed findings.
"""

from __future__ import annotations

import json
import sqlite3

# Design D8 — fixed, operator-set. The CSV is last (not first): it's an
# unreviewed third-party wordlist, not curated operator data, and gets no
# exemption from the known-set filter or merge priority.
SOURCE_PRIORITY = ("ntnu", "a1_31k", "core6k", "freq6k", "herpaberget")

MERGE_FIELDS = (
    "note_type",
    "text",
    "pos",
    "translations",
    "context_text",
    "transcription",
    "inflections",
    "audio_ref",
)

_CEFR_TAG_PREFIX = "CEFR::"


def _priority_index(source: str) -> int:
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)


def _is_empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _cefr_tag(tags: list[str]) -> str | None:
    for tag in tags:
        if tag.startswith(_CEFR_TAG_PREFIX):
            return tag
    return None


def merge_group(rows: list[dict]) -> tuple[dict, dict, dict, dict]:
    """`rows` is every normalized row (plus its source, raw tags, and
    order-signal data) sharing one lexeme signature. Returns
    (fields, sources, conflicts, order_key).

    `fields`: the merged field values (task 5.2).
    `sources`: field -> the source whose value won.
    `conflicts`: field -> list of {source, value} for every losing
    non-empty value that disagreed with the winner (task 5.3).
    `order_key`: the review ordering signal (task 5.5)."""
    ordered_rows = sorted(rows, key=lambda r: _priority_index(r["source"]))

    fields: dict = {}
    sources: dict = {}
    conflicts: dict = {}

    for field in MERGE_FIELDS:
        winner_value = None
        winner_source = None
        losers: list[dict] = []
        for row in ordered_rows:
            value = row[field]
            if _is_empty(value):
                continue
            if winner_value is None:
                winner_value = value
                winner_source = row["source"]
            elif value != winner_value:
                losers.append({"source": row["source"], "value": value})
        if winner_value is not None:
            fields[field] = winner_value
            sources[field] = winner_source
            if losers:
                conflicts[field] = losers

    frequency_index = None
    cefr_tag = None
    chapter = None
    for row in ordered_rows:
        order_signal = row["order_signal"]
        if frequency_index is None and order_signal.get("frequency_index") is not None:
            frequency_index = order_signal["frequency_index"]
        if cefr_tag is None:
            found = _cefr_tag(row["tags"])
            if found is not None:
                cefr_tag = found
        if chapter is None and order_signal.get("kapittel"):
            chapter = order_signal["kapittel"]

    order_key = {"frequency_index": frequency_index, "cefr": cefr_tag, "chapter": chapter}

    return fields, sources, conflicts, order_key


def order_sort_key(order_key: dict) -> tuple:
    """A candidate with no ranking signal sorts after one that has any
    (task 5.5's review-ordering requirement) — `None` always sorts last
    within its own tier via the `(has_signal, value)` pairing below."""
    frequency_index = order_key.get("frequency_index")
    cefr = order_key.get("cefr")
    chapter = order_key.get("chapter")
    return (
        (0, frequency_index) if frequency_index is not None else (1, 0),
        (0, cefr) if cefr is not None else (1, ""),
        (0, chapter) if chapter is not None else (1, ""),
    )


def run(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    import store

    rows = conn.execute(
        """
        SELECT n.id AS normalized_id, n.raw_note_id, n.source, n.note_type, n.text, n.pos,
               n.translations_json, n.context_text, n.transcription, n.inflections_json,
               n.audio_ref, n.order_signal_json, s.signature_key
        FROM normalized n
        JOIN signature s ON s.normalized_id = n.id
        """
    ).fetchall()
    count_in = len(rows)

    raw_note_tags: dict[int, list[str]] = {}
    for raw_row in conn.execute("SELECT id, tags_json FROM raw_note").fetchall():
        raw_note_tags[raw_row["id"]] = json.loads(raw_row["tags_json"])

    verdict_by_signature: dict[str, dict] = {}
    for v_row in conn.execute("SELECT signature_key, verdict, rule, evidence_json FROM verdict").fetchall():
        verdict_by_signature.setdefault(
            v_row["signature_key"],
            {"verdict": v_row["verdict"], "rule": v_row["rule"], "evidence": json.loads(v_row["evidence_json"])},
        )

    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["signature_key"], []).append(
            {
                "source": row["source"],
                "note_type": row["note_type"],
                "text": row["text"],
                "pos": row["pos"],
                "translations": json.loads(row["translations_json"]),
                "context_text": row["context_text"],
                "transcription": row["transcription"],
                "inflections": json.loads(row["inflections_json"]),
                "audio_ref": row["audio_ref"],
                "order_signal": json.loads(row["order_signal_json"]),
                "tags": raw_note_tags.get(row["raw_note_id"], []),
            }
        )

    store.replace_stage_table(conn, "merge")
    for signature_key, group_rows in groups.items():
        fields, sources, conflicts, order_key = merge_group(group_rows)
        verdict_info = verdict_by_signature.get(signature_key, {"verdict": "import", "rule": None, "evidence": {}})
        conn.execute(
            """
            INSERT INTO candidate (
                run_id, signature_key, fields_json, sources_json, conflicts_json,
                verdict, verdict_evidence_json, order_key_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                signature_key,
                json.dumps(fields, ensure_ascii=False),
                json.dumps(sources, ensure_ascii=False),
                json.dumps(conflicts, ensure_ascii=False),
                verdict_info["verdict"],
                json.dumps({"rule": verdict_info["rule"], **verdict_info["evidence"]}, ensure_ascii=False),
                json.dumps(order_key, ensure_ascii=False),
            ),
        )
    conn.commit()

    count_out = len(groups)
    return count_in, count_out, 0
