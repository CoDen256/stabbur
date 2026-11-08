## Why

A note's provenance is currently expressed by a single nullable column,
`capture_id`. That encodes exactly one origin story (promoted from a
hover-translate capture) and leaves every other note indistinguishable: a
note hand-authored in the triage UI and a note whose provenance was simply
never recorded both have `capture_id = NULL`. "Null" is a bad way to say
"a human typed this," because it cannot be told apart from "we don't know."

A bulk import of external vocabulary sources (`bulk-import-anki-csv`) is
about to add thousands of notes from a third kind of origin. Before that
lands, every note needs to assert positively where it came from, and the
operator needs to filter the notes browser by it — otherwise an import of
~7,500 drafts makes hand-authored work unfindable, and there is no way to
answer "which of these did I write myself?"

This change is deliberately scoped to the provenance field and its filter
only, with no import machinery, so it can be implemented independently of
and in parallel with the import work that motivates it.

## What Changes

- **`origin` column on `notes`**: a required enum, `manual | capture |
  import`, forming a total partition — every note falls in exactly one
  bucket and nothing hides in a null.
- **`import_ref` column on `notes`**: nullable JSONB recording which
  external source a note was imported from (`{source, source_note_id,
  run_id}`). No foreign key — the import tool's candidate store is a local,
  non-service artifact that stabbur must not depend on (D42/D43).
- **Integrity constraints tying origin to its evidence**: `origin=capture`
  requires `capture_id`; `origin=import` requires `import_ref`;
  `origin=manual` requires both to be null. An origin claim cannot be made
  without the provenance to back it.
- **Backfill of existing rows**: `capture_id IS NOT NULL → capture`,
  otherwise `manual`.
- **`origin` is immutable after creation.** `PATCH` rejects any attempt to
  change it — rewriting provenance is falsifying a record, not editing a
  field.
- **Authoring API accepts and validates `origin`/`import_ref`**, and derives
  `origin` when omitted (`capture` if `capture_id` is present, else
  `manual`) so existing clients keep working unchanged. `import` is never
  derived; it must be stated explicitly.
- **`GET /api/notes/authoring` gains an `origin` filter**, alongside the
  existing `status`/`type`/`pos`/`grammar_rule_id`/`q` filters.
- **Notes browser gains an origin filter control**, alongside status and
  type.
- **The public read API is untouched.** `origin` is operator-facing
  metadata; `GET /api/notes` keeps its exact current response shape, because
  whether a note was typed or imported is none of Mjølnir's business (D44).

## Capabilities

### Modified Capabilities
- `notes-schema`: provenance becomes a required, positively-asserted
  property of every note with integrity constraints, rather than one
  optional nullable column. A requirement-level change to the data model.
- `notes-authoring`: the create/patch contract gains a validated
  provenance field with immutability rules, and the authoring list gains a
  new filter dimension.
- `notes-browser`: the operator can filter the list by origin, which is a
  new requirement-level capability of the browser, not an internal detail.

### Unchanged (explicitly)
- `notes-read-api`: no change to request or response shape.

## Impact

- **Schema** (`db/models.py`, new Alembic migration): two new columns on
  `notes`, three new check constraints, one data backfill. The backfill is
  derivable from existing data, so the migration is safe to run forward on
  live data; `origin` is `NOT NULL` only after the backfill populates it.
- **API** (`routes/notes.py`): `create_note` accepts/derives/validates
  `origin` + `import_ref`; `patch_note` rejects `origin` and `import_ref`
  changes; `_serialize_authoring` exposes both; `list_notes_authoring`
  gains the `origin` query parameter. `_serialize_public` and `list_notes`
  are not touched.
- **UI** (`ui/index.html`, `ui/ui.js`, `ui/ui.css`): an origin filter
  control in the notes browser; origin shown read-only on the note editor
  (it cannot be edited, so it is displayed, not offered as an input).
- **Tests** (`tests/test_notes_authoring.py`,
  `tests/test_notes_authoring_list.py`, `tests/test_models.py`): constraint
  coverage, derivation, immutability, filter behaviour, and an explicit
  assertion that the public read API's shape is unchanged.
- No dependency on `bulk-import-anki-csv`. That change consumes this one's
  API; this one does not know it exists.
