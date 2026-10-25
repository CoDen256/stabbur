"""
db/models.py — SQLAlchemy ORM models for stabbur's own Postgres database.

D42/D43: no cross-service foreign keys — this schema never references
mjolnir/hub's tables, and carries nothing deck-, id-, or occurrence-shaped.
`grammar_rule_id` -> `grammar_rule.id` is a same-database FK (both tables
live here), not a cross-service one.

Every column here traces back to `tun/docs/03-data-model.md`'s `note`
schema exactly — no speculative columns, no narrowing either. Two additions
beyond that sketch, both flagged as open questions in this change's
design.md and resolved during implementation (recorded there, task 4.4/5.4):

- `updated_at`: cheap to add now, awkward to retrofit later if a future
  consumer wants to filter on "changed since" rather than only "created
  since" (`notes-read-api`'s `since` filters on this column).
- `deleted_at`: the concrete tombstone mechanism for `notes-schema`'s
  permanence rule. A `draft` note's row is hard-deleted; a `ready` note
  (therefore possibly already pulled) gets `deleted_at` set instead — its
  id stays resolvable, excluded from the read API's listing.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Sequence, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NOTE_TYPES = ("word", "expression", "listening", "pronunciation", "grammar")
NOTE_STATUSES = ("draft", "ready")


class Base(DeclarativeBase):
    pass


class GrammarRule(Base):
    """Shared `X` across `type=grammar` notes (03-data-model.md) — multiple
    notes reference the same row so the explanation is stored once."""

    __tablename__ = "grammar_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    html: Mapped[str] = mapped_column(Text, nullable=False)


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint(f"type IN {NOTE_TYPES!r}", name="ck_notes_type"),
        CheckConstraint(f"status IN {NOTE_STATUSES!r}", name="ck_notes_status"),
        CheckConstraint(
            "type != 'grammar' OR grammar_rule_id IS NOT NULL", name="ck_notes_grammar_requires_rule"
        ),
    )

    # A random id, not content-derived and not sequential — permanent even
    # once tombstoned (notes-schema spec), and never reused.
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # Set only when a `ready` note is deleted (tombstone); null otherwise.
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Provenance; null for hand-authored entries. No FK — P7's `captures`
    # table does not exist yet in this change.
    capture_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    type: Mapped[str] = mapped_column(Text, nullable=False)
    source_lang: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    translations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    pos: Mapped[str | None] = mapped_column(Text, nullable=True)
    lemma: Mapped[str | None] = mapped_column(Text, nullable=True)
    inflections: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # A reference (sha256), not the bytes (D-N2) — not required for
    # status=ready, only for Mjolnir eligibility, which stabbur never checks.
    audio_blob: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_sel_ms: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    grammar_rule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("grammar_rule.id"), nullable=True
    )

    # stabbur-internal display number only — unrelated to Mjolnir's card_no.
    seq: Mapped[int] = mapped_column(Integer, Sequence("notes_seq"), nullable=False, unique=True)

    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
