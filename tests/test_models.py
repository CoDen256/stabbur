"""Task 1.4/1.5 — schema-level tests: the five note types and their
documented inflection shapes, status validation, and tombstone behavior."""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from db.models import GrammarRule, Note
from db.session import get_sessionmaker

INFLECTION_SHAPES = {
    "substantiv": {"article": "et", "sg_indef": "hus", "sg_def": "huset", "pl_indef": "hus", "pl_def": "husene"},
    "adjektiv": {"positiv": "fin", "nøytrum": "fint", "flertall": "fine", "komparativ": "finere", "superlativ": "finest"},
    "verb": {"infinitiv": "å gå", "presens": "går", "preteritum": "gikk", "perfektum": "har gått"},
    "adverb": {"form": "fort"},
}


@pytest.mark.parametrize(
    "type_,pos,inflections",
    [
        ("word", "substantiv", INFLECTION_SHAPES["substantiv"]),
        ("word", "adjektiv", INFLECTION_SHAPES["adjektiv"]),
        ("word", "verb", INFLECTION_SHAPES["verb"]),
        ("word", "adverb", INFLECTION_SHAPES["adverb"]),
        ("expression", None, {}),
    ],
)
def test_create_note_with_each_type_and_inflection_shape(type_, pos, inflections):
    Session = get_sessionmaker()
    with Session() as db:
        note = Note(
            type=type_,
            source_lang="no",
            text="hus",
            pos=pos,
            inflections=inflections,
            translations=[{"lang": "en", "text": "house"}],
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        assert note.inflections == inflections
        assert note.status == "draft"


def test_listening_and_pronunciation_types():
    Session = get_sessionmaker()
    with Session() as db:
        for type_ in ("listening", "pronunciation"):
            note = Note(type=type_, source_lang="no", text="Han gikk til butikken.")
            db.add(note)
        db.commit()


def test_grammar_type_requires_grammar_rule_id():
    Session = get_sessionmaker()
    with Session() as db:
        note = Note(type="grammar", source_lang="no", text="Oversett: I am happy")
        db.add(note)
        with pytest.raises(IntegrityError):
            db.commit()


def test_grammar_type_with_rule_id_succeeds():
    Session = get_sessionmaker()
    with Session() as db:
        rule = GrammarRule(title="Presens", html="<p>Norwegian present tense...</p>")
        db.add(rule)
        db.flush()
        note = Note(type="grammar", source_lang="no", text="Oversett: I am happy", grammar_rule_id=rule.id)
        db.add(note)
        db.commit()
        db.refresh(note)
        assert note.grammar_rule_id == rule.id


def test_invalid_status_is_rejected():
    Session = get_sessionmaker()
    with Session() as db:
        note = Note(type="word", source_lang="no", text="hus", status="published")
        db.add(note)
        with pytest.raises(IntegrityError):
            db.commit()


def test_ready_status_allows_null_audio_blob():
    Session = get_sessionmaker()
    with Session() as db:
        note = Note(type="word", source_lang="no", text="hus", status="ready", audio_blob=None)
        db.add(note)
        db.commit()
        db.refresh(note)
        assert note.status == "ready"
        assert note.audio_blob is None


def test_deleting_draft_note_removes_the_row():
    Session = get_sessionmaker()
    with Session() as db:
        note = Note(type="word", source_lang="no", text="hus", status="draft")
        db.add(note)
        db.commit()
        note_id = note.id
        db.delete(note)
        db.commit()
        assert db.get(Note, note_id) is None


def test_deleting_ready_note_does_not_free_its_id():
    """notes-schema spec: a `ready` note's id must remain resolvable as a
    tombstone rather than being freed for reuse — implemented as a
    `deleted_at` marker rather than row removal (design.md D-N3/Open
    Questions)."""
    Session = get_sessionmaker()
    with Session() as db:
        note = Note(type="word", source_lang="no", text="hus", status="ready")
        db.add(note)
        db.commit()
        note_id = note.id

        note.deleted_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

    with Session() as db:
        tombstoned = db.get(Note, note_id)
        assert tombstoned is not None
        assert tombstoned.deleted_at is not None
