## 1. Schema

- [ ] 1.1 `db/models.py`: add `NOTE_ORIGINS = ("manual", "capture", "import")` next to the existing `NOTE_TYPES` / `NOTE_STATUSES` tuples.
- [ ] 1.2 `db/models.py`: add `origin: Mapped[str]` (`Text`, `nullable=False`) and `import_ref: Mapped[dict | None]` (`JSONB`, `nullable=True`) to `Note`, with a comment explaining that `import_ref` is a reference and deliberately not a FK (design D3).
- [ ] 1.3 `db/models.py`: add four constraints to `Note.__table_args__`, written in the same shape as the existing `ck_notes_grammar_requires_rule`:
  - `ck_notes_origin` — `origin IN NOTE_ORIGINS`
  - `ck_notes_capture_origin_requires_capture_id` — `origin <> 'capture' OR capture_id IS NOT NULL`
  - `ck_notes_import_origin_requires_import_ref` — `origin <> 'import' OR import_ref IS NOT NULL`
  - `ck_notes_manual_origin_has_no_provenance` — `origin <> 'manual' OR (capture_id IS NULL AND import_ref IS NULL)`
- [ ] 1.4 Update the module docstring in `db/models.py` — it currently enumerates the two columns that go beyond `tun/docs/03-data-model.md`'s sketch (`updated_at`, `deleted_at`). `origin` and `import_ref` are a third and fourth; record them there with the same reasoning style, referencing this change.

## 2. Migration

- [ ] 2.1 New Alembic revision, down-revision `f254ab80b2e6`. Four ordered steps per design D7 — do not collapse them.
- [ ] 2.2 Step 1: `add_column` both `origin` (nullable at this point) and `import_ref`.
- [ ] 2.3 Step 2: backfill — `UPDATE notes SET origin = CASE WHEN capture_id IS NOT NULL THEN 'capture' ELSE 'manual' END`.
- [ ] 2.4 Step 3: `alter_column('origin', nullable=False)`.
- [ ] 2.5 Step 4: create all four check constraints (after the backfill, so they cannot fail against unpopulated rows).
- [ ] 2.6 Downgrade: drop the four constraints, then both columns.

## 3. API

- [ ] 3.1 `routes/notes.py` `create_note`: derive/validate `origin` per design D6 — explicit value wins; omitted derives `capture` if `capture_id` else `manual`; `import_ref` present with no explicit `origin` is a `400`; `origin=import` with no `import_ref` is a `400`.
- [ ] 3.2 `routes/notes.py` `create_note`: pass `origin` and `import_ref` through to the `Note(...)` constructor.
- [ ] 3.3 `routes/notes.py` `patch_note`: reject `origin` or `import_ref` in the body with a `400` when the value differs from the stored one; accept silently when identical (design D5's round-trip allowance).
- [ ] 3.4 `routes/notes.py` `_serialize_authoring`: add `origin` and `import_ref`.
- [ ] 3.5 `routes/notes.py` `list_notes_authoring`: add an `origin` query parameter — validate against `NOTE_ORIGINS` returning `400` on a bad value (same shape as the existing `status`/`type` validation), then one more `stmt.where(Note.origin == origin)` clause.
- [ ] 3.6 Confirm `_serialize_public` and `list_notes` are **not** touched (design D8).
- [ ] 3.7 `_integrity_error_message`: map the four new constraint names to readable messages, consistent with how existing constraints are handled there.

## 4. UI

- [ ] 4.1 `ui/index.html`: origin filter control in the notes browser filter row, alongside the existing status and type filters — options: all / manual / capture / import.
- [ ] 4.2 `ui/ui.js`: include `origin` in the authoring-list query string when the filter is set; omit the parameter entirely when "all" is selected.
- [ ] 4.3 `ui/ui.js`: render origin read-only in the note editor (design D9) — for `origin=import`, show the source name from `import_ref.source` rather than raw JSON; never render an editable control.
- [ ] 4.4 `ui/ui.css`: styling for the new filter control and the read-only origin display, matching the surrounding filter row and metadata styling.

## 5. Tests

- [ ] 5.1 `tests/test_models.py`: each of the four constraints rejects its violating case, and each origin's valid shape is accepted.
- [ ] 5.2 `tests/test_notes_authoring.py`: derivation — omitted origin with no capture → `manual`; omitted with `capture_id` → `capture`; `import_ref` with omitted origin → `400`; `origin=import` without `import_ref` → `400`.
- [ ] 5.3 `tests/test_notes_authoring.py`: immutability — patching `origin` to a different value → `400`; patching content fields on an imported note succeeds and leaves `origin=import`; patching with the identical `origin` value → accepted.
- [ ] 5.4 `tests/test_notes_authoring_list.py`: `origin` filter alone, combined with `status`, invalid value → `400`, and absent → all origins returned.
- [ ] 5.5 `tests/test_notes_read_api.py`: assert the public response contains neither `origin` nor `import_ref`, and that passing `origin` as a query parameter does not change which notes are returned. This guards design D8 against future accidental widening.
- [ ] 5.6 Full suite green against a real throwaway Postgres container (the existing convention in this repo), not SQLite — the check constraints and JSONB column must be exercised on the real engine.

## 6. Migration verification

- [ ] 6.1 Against a copy of live data: row counts by `origin` after backfill sum to the pre-migration total, with zero nulls.
- [ ] 6.2 Confirm no pre-existing row has both a `capture_id` and evidence of being hand-authored (design's stated risk) — if any exist, record the judgement made rather than letting the `CASE` decide silently.
- [ ] 6.3 Verify downgrade then re-upgrade on the same copy leaves the table in the expected state.
