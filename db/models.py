"""
db/models.py — SQLAlchemy ORM models for stabbur's own Postgres database.

D42/D43: no cross-service foreign keys — this schema never references
mjolnir/hub's tables, and carries nothing deck-, id-, or occurrence-shaped.
`grammar_rule_id` -> `grammar_rule.id` is a same-database FK (both tables
live here), not a cross-service one.

Every column here traces back to `tun/docs/03-data-model.md`'s `note`
schema exactly — no speculative columns, no narrowing either. Four additions
beyond that sketch, flagged as open questions in their originating change's
design.md and resolved during implementation:

- `updated_at`: cheap to add now, awkward to retrofit later if a future
  consumer wants to filter on "changed since" rather than only "created
  since" (`notes-read-api`'s `since` filters on this column).
- `deleted_at`: the concrete tombstone mechanism for `notes-schema`'s
  permanence rule. A `draft` note's row is hard-deleted; a `ready` note
  (therefore possibly already pulled) gets `deleted_at` set instead — its
  id stays resolvable, excluded from the read API's listing.
- `origin` (note-origin-provenance): every note positively asserts where
  it came from (`manual`/`capture`/`import`) instead of leaving provenance
  to be inferred from `capture_id`'s nullness.
- `import_ref` (note-origin-provenance): a reference, not a foreign key,
  to the external source an `origin=import` note was imported from — the
  import tool's candidate store is a local, non-service artifact.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Sequence, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NOTE_TYPES = ("word", "expression", "listening", "pronunciation", "grammar")
NOTE_STATUSES = ("draft", "ready")
NOTE_ORIGINS = ("manual", "capture", "import")


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
        CheckConstraint(f"origin IN {NOTE_ORIGINS!r}", name="ck_notes_origin"),
        CheckConstraint(
            "origin <> 'capture' OR capture_id IS NOT NULL", name="ck_notes_capture_origin_requires_capture_id"
        ),
        CheckConstraint(
            "origin <> 'import' OR import_ref IS NOT NULL", name="ck_notes_import_origin_requires_import_ref"
        ),
        CheckConstraint(
            "origin <> 'manual' OR (capture_id IS NULL AND import_ref IS NULL)",
            name="ck_notes_manual_origin_has_no_provenance",
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

    # Positively asserts where a note came from — see NOTE_ORIGINS. Never
    # null; "capture"/"import" is backed by capture_id/import_ref via the
    # check constraints above, and immutable once set (routes/notes.py).
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    # A reference (source/source_note_id/run_id), not a foreign key —
    # the import tool's candidate store is a local, non-service artifact
    # that stabbur must not depend on (design.md D3, D42/D43).
    # none_as_null=True: without it, SQLAlchemy encodes a Python `None`
    # here as the JSON scalar `null` rather than a SQL NULL, which silently
    # defeats ck_notes_manual_origin_has_no_provenance's `IS NULL` check.
    import_ref: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)

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


SETTINGS_TRANSLATION_MERGE_MODES = ("append", "separate")
# note-triage design D6: whether prefill runs the moment a triage note is
# presented, or only when the operator presses the fill control.
SETTINGS_PREFILL_TIMINGS = ("on_open", "on_demand")


class Settings(Base):
    """operator-settings (design D1/D2): a single operator-preferences row.
    stabbur is single-operator behind one shared token, so preferences are
    singular by construction — `id` is pinned to 1 and the check constraint
    below is the entire "at most one row" guard, no further uniqueness
    machinery needed.

    Every scalar preference is nullable: unset means "use the code-level
    default" (settings_store.py), not "row doesn't exist yet" — the row is
    created the first time any preference is written, never seeded by the
    migration (D2 — a seeded row would freeze defaults at migration time)."""

    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_settings_singleton"),
        CheckConstraint(
            f"translation_merge_mode IS NULL OR translation_merge_mode IN {SETTINGS_TRANSLATION_MERGE_MODES!r}",
            name="ck_settings_merge_mode",
        ),
        CheckConstraint(
            f"prefill_timing IS NULL OR prefill_timing IN {SETTINGS_PREFILL_TIMINGS!r}",
            name="ck_settings_prefill_timing",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Per enrichment kind: {"order": [provider, ...], "disabled": [provider, ...]}.
    # Ordering and enablement only (D43) — never provider definitions,
    # endpoints, or credentials, which stay smia's own (design D3/Non-Goals).
    provider_prefs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    translation_merge_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_prefill: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    default_target_langs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    prefill_timing: Mapped[str | None] = mapped_column(Text, nullable=True)
