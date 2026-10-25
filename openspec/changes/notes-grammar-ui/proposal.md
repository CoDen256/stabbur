## Why

`p4-notes` (archived 2026-10-25) shipped a minimal authoring surface:
create a note, find one by id, nothing more. That was correct for reaching
P4's finish line fast, but it is not usable as a real tool — there is no way
to browse what exists, no way to tell what's ready vs. not without querying
the database by hand, and no way to listen to or adjust a note's audio
without going outside the UI entirely. This change builds the real tool
`tun/docs/13-operator-console-ux.md` specifies (mockup linked from that doc),
without touching anything the original `p4-notes` scope deliberately
excluded (capture ingestion, enrichment, triage workflow — still P7/P8, still
not here).

## What Changes

- **Notes become a real browsable list**: filter by status/type, sort,
  full-text search across content/translation, click straight through to
  edit — no id-hunting.
- **The note editor gains**: an audio player with a draggable trim range
  over a waveform (not numeric fields), a "replace audio" action, a raw-JSON
  toggle alongside the structured form, and — on *creation* — the inflection
  fields reshape live based on the chosen part of speech, instead of
  presenting a blank JSON-shaped form to fill in by hand.
- **Grammar rules get the same treatment**: a browsable, sortable,
  filterable list; a detail/edit page; a reverse "used by N notes" view;
  delete blocked while any note still references the rule; a dedicated
  creation form.
- **BREAKING**: none — this only adds surface area to an existing, narrow
  authoring UI with no other consumers yet.

Explicitly **not** in this change, so it isn't mistaken for scope creep:
capture ingestion (`POST /captures`, hover-translate integration — P7), the
triage inbox / enrichment suggestions / dedup (P8). `notes-authoring`'s
existing "minimal surface, not a triage workflow" requirement still holds —
this change makes the minimal surface pleasant to use, it does not turn it
into the triage workflow that requirement explicitly excludes.

## Capabilities

### New Capabilities
- `notes-browser`: the filterable, sortable, searchable notes list.
- `note-editor`: the detail/edit page — structured fields, audio
  player/trim/replace, raw-JSON view, PoS-driven inflection prefill on
  creation.
- `grammar-management`: grammar rule list, detail/edit, reverse usage
  lookup, delete-while-unused-only, creation form.

### Modified Capabilities
<!-- None. `notes-authoring`'s existing requirements (create/read/update/
     conditional-delete, minimal-surface-not-a-triage-workflow) are
     unchanged — this change adds a UI and new behavior on top of them,
     it doesn't change what they require. -->

## Impact

- **New UI code** in `stabbur`'s existing `ui/` — no new backend service,
  this extends the Flask app `p4-notes` already built.
- **Possible new/extended API endpoints** to support list filtering/sorting
  and the grammar reverse-usage query — additive to `notes-read-api` and
  `notes-authoring`'s existing routes, not a breaking change to either.
- **Depends on** `mjolnir`'s `small-fixes-audio-trim-drain-order` only
  loosely: that change makes `builder` *respect* `audio_sel_ms`; this change
  is what lets an operator *set* it with a real trim UI instead of raw
  millisecond numbers. Either can ship first; the trim range this UI writes
  already matches the field `03-data-model.md` specifies, independent of
  whether `builder` reads it yet.
- **No change to `blob-storage`'s or `notes-schema`'s requirements** — the
  "replace audio" action calls the existing `POST /blobs` upload endpoint;
  it doesn't need a new one.
