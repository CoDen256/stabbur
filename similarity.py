"""
similarity.py — the three similar-notes signals (`similar-notes-merge`
design D1): spelling via `pg_trgm`, morphology via shared inflected
surface forms, and semantics via shared normalised translations.

Each signal is its own query, run on demand for one note — not an
all-pairs precomputation (design D2). A note matched by more than one
signal is still looked up once by `find_similar` below, carrying every
reason it matched for (tasks.md 3.5).
"""

from __future__ import annotations

import os

from sqlalchemy import func, select, text

from db.models import Note

# design.md's Risks/Open Questions: the 0.4 threshold was measured on the
# import candidate store, not the real `notes` table, and may need
# revisiting — configurable rather than compiled in (tasks.md 3.1).
SIMILARITY_THRESHOLD = float(os.environ.get("STABBUR_SIMILAR_NOTES_THRESHOLD", "0.4"))

# The grammatical article (en/et/ei) is excluded from the morphology
# signal — sharing it would relate thousands of unrelated nouns (design
# D1, spec requirement).
_MORPHOLOGY_EXCLUDED_KEY = "article"

_LEADING_TRANSLATION_WORDS = ("a", "an", "the", "to")


def normalized_text_expr(column):
    """Article/infinitive-stripped, lowercased form of a text expression.
    Must match the migration's GIN index expression exactly (design D2;
    see `alembic/versions/88c04d15a436_similar_notes_pg_trgm.py`), so that
    `å oppleve` and `oppleve` compare as the same string and the index can
    serve the query."""
    stripped = func.regexp_replace(column, r"^å\s+", "")
    stripped = func.regexp_replace(stripped, r"^(en|et|ei)\s+", "")
    return func.lower(stripped)


def normalize_translation(value: str) -> str:
    """Lowercase, strip a single leading a/an/the/to (tasks.md 3.4)."""
    normalized = value.strip().lower()
    for prefix in _LEADING_TRANSLATION_WORDS:
        marker = f"{prefix} "
        if normalized.startswith(marker):
            return normalized[len(marker):]
    return normalized


def spelling_matches(db, note: Note) -> dict[str, float]:
    """note id -> trigram similarity score, for notes spelled alike.
    Excludes `listening` notes (sentence-length text; design non-goal)
    and notes of a different `source_lang` (non-goal, cheap to exclude)."""
    if note.type == "listening":
        return {}

    similarity_expr = func.similarity(normalized_text_expr(Note.text), normalized_text_expr(note.text))
    stmt = select(Note.id, similarity_expr).where(
        Note.id != note.id,
        Note.source_lang == note.source_lang,
        Note.type != "listening",
        Note.deleted_at.is_(None),
        similarity_expr >= SIMILARITY_THRESHOLD,
    )
    return {row[0]: float(row[1]) for row in db.execute(stmt).all()}


def morphology_matches(db, note: Note) -> set[str]:
    """note ids sharing an inflected surface form with `note`, excluding
    the `article` key."""
    values = {
        v
        for k, v in (note.inflections or {}).items()
        if k != _MORPHOLOGY_EXCLUDED_KEY and isinstance(v, str) and v
    }
    if not values:
        return set()

    stmt = text(
        """
        SELECT DISTINCT n.id
        FROM notes n, jsonb_each_text(n.inflections) kv
        WHERE n.id != :note_id
          AND n.source_lang = :source_lang
          AND n.deleted_at IS NULL
          AND kv.key != :excluded_key
          AND kv.value = ANY(:values)
        """
    )
    rows = db.execute(
        stmt,
        {
            "note_id": note.id,
            "source_lang": note.source_lang,
            "excluded_key": _MORPHOLOGY_EXCLUDED_KEY,
            "values": list(values),
        },
    )
    return {row[0] for row in rows}


def semantic_matches(db, note: Note) -> set[str]:
    """note ids sharing a normalised translation with `note`."""
    normalized = {
        normalize_translation(t["text"])
        for t in (note.translations or [])
        if t.get("text")
    }
    if not normalized:
        return set()

    stmt = text(
        """
        SELECT DISTINCT n.id
        FROM notes n, jsonb_array_elements(n.translations) t
        WHERE n.id != :note_id
          AND n.source_lang = :source_lang
          AND n.deleted_at IS NULL
          AND lower(regexp_replace(t->>'text', '^(a|an|the|to)\\s+', '')) = ANY(:normalized)
        """
    )
    rows = db.execute(
        stmt, {"note_id": note.id, "source_lang": note.source_lang, "normalized": list(normalized)}
    )
    return {row[0] for row in rows}


def find_similar(db, note: Note) -> list[dict]:
    """Every note related to `note` by at least one signal, each appearing
    once with every signal that matched it (tasks.md 3.5/3.6)."""
    spelling = spelling_matches(db, note)
    morphology = morphology_matches(db, note)
    semantic = semantic_matches(db, note)

    signals_by_id: dict[str, dict] = {}
    for note_id, score in spelling.items():
        signals_by_id.setdefault(note_id, {})["spelling"] = score
    for note_id in morphology:
        signals_by_id.setdefault(note_id, {})["morphology"] = True
    for note_id in semantic:
        signals_by_id.setdefault(note_id, {})["semantic"] = True

    if not signals_by_id:
        return []

    matched_notes = db.scalars(select(Note).where(Note.id.in_(signals_by_id.keys()))).all()
    by_id = {n.id: n for n in matched_notes}

    return [
        {"note": by_id[note_id], "signals": signals}
        for note_id, signals in signals_by_id.items()
        if note_id in by_id
    ]
