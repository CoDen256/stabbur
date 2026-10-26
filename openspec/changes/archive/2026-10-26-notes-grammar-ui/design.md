## Context

Read in order:

1. `tun/docs/13-operator-console-ux.md` — the UX direction, and the mockup
   link it carries. The stabbur half of that mockup is what this change
   builds.
2. `tun/docs/03-data-model.md` — the exact note/grammar_rule fields, the
   five note types' inflection shapes, `audio_sel_ms`'s meaning (a selection
   *inside* a wider blob, not a replacement for it).
3. **`routes/notes.py`, read in full before adding anything.** Two findings
   that shape this change directly:
   - `GET /api/notes` is `notes-read-api`'s contract — hard-locked to
     `status=ready`, by design, forever (D44). **Do not relax this filter.**
     The authoring list needs drafts too, which means a *separate* route,
     not a parameter added to this one.
   - Grammar rules only have `POST` (create) and `GET` (list) today. There is
     no single-rule `GET`/`PATCH`/`DELETE` at all — the detail/edit/delete
     pages this change adds are new backend routes, not just new UI over
     existing ones.
4. `ui/ui.js` / `ui/index.html` — the existing vanilla-JS, no-framework
   style. This change extends that style; it does not introduce a frontend
   framework or build step (matches `smia`'s and `mjolnir`'s UIs — D46's
   "vendored CSS, not a package" convention, applied to JS too).

## Goals / Non-Goals

**Goals:**
- Every stabbur page in `13-operator-console-ux.md`'s mockup, built against
  the real API.
- A clean separation between the frozen public contract (`notes-read-api`)
  and the new authoring-browse surface — the former must not grow a
  side-channel for drafts, ever.
- Grammar rules reach parity with notes: full CRUD, not just create+list.

**Non-Goals:**
- Any change to `notes-read-api`'s existing requirements or route.
- Capture ingestion, enrichment, triage — still P7/P8, as the proposal
  states.
- A waveform-rendering audio library. See D-S2 below for why a lighter
  approach is enough here.

## Decisions

### D-S1 — a separate authoring-list route, not a parameter on the public one

```
GET /api/notes                    — UNCHANGED. status=ready always, D44's
                                     contract, mjolnir's p4-builder fixture
                                     is built against this exact shape.
GET /api/notes/authoring          — NEW. Every status, filter by
                                     status/type/pos, sort, search text.
                                     Operator-only, never called by builder.
```

Keeping these as two routes, not one route with a "include drafts" flag,
makes it structurally impossible for a future change to accidentally widen
the public contract by relaxing a shared query path — the public route's
code never changes.

### D-S2 — audio trim UI: numeric range with waveform display, not a trim library

The mockup shows a draggable two-handle range over a waveform. Building a
real interactive waveform (decode audio, render peaks, handle drag) is
real frontend work with no existing dependency to lean on in this
no-framework codebase. **Chosen approach**: render a static waveform preview
(client-side, via the Web Audio API's `decodeAudioData` + a `<canvas>`, no
new dependency — browsers already have everything needed) with two draggable
range handles backed by plain numeric `audio_sel_ms` values underneath — the
visual is real, but the interaction model is "drag a handle, the underlying
number updates," not a third-party trim-widget library. A "preview trim"
button plays back the selected range using the already-loaded `<audio>`
element's `currentTime`/timed-pause, no new playback dependency either.

### D-S3 — grammar rules need real CRUD, not just the UI calling existing routes

Since `GET/PATCH/DELETE /api/grammar_rules/<id>` don't exist, this change
adds them, matching `routes/notes.py`'s existing per-resource pattern
exactly. Delete must check for referencing notes first (`notes-schema`'s
existing FK relationship) and refuse with a clear count, not a raw
integrity-constraint error surfacing to the UI.

### D-S4 — PoS-driven inflection prefill is a client-side form behavior, not a new endpoint

The five note types' inflection shapes are already fully enumerated in
`03-data-model.md` and are small, fixed, and client-knowable (substantiv:
5 fields, adjektiv: 5, verb: 4, adverb: 1, other: none). Hardcode this
mapping in the creation form's JS — no new endpoint needed to "ask the
server what fields a PoS needs."

## Risks / Trade-offs

- **A canvas-rendered waveform without a library is more code than a drop-in
  widget, for a nicer result than numeric-only fields.** → Scope it as a
  static peak-preview + draggable overlay, not a full scrubbing/zooming
  audio editor — the goal is "see roughly where the cut is," not a DAW.
- **The new authoring-list route duplicating some query shape from the
  public one** → acceptable, explicitly, per D-S1 — the duplication is what
  keeps the public contract's code path untouched and un-widenable by
  accident.
- **Grammar delete racing a note being created with that rule's id between
  the "check for references" query and the actual delete** → wrap both in
  one transaction (a single `SELECT ... FOR UPDATE` or just a transactional
  check-then-delete) rather than two separate round-trips.

## Migration Plan

No schema change (every field this UI touches already exists —
`audio_sel_ms`, `updated_at`, `deleted_at` all shipped in `p4-notes`/D82).
Pure additive UI + new routes:

1. `GET /api/notes/authoring` + the notes list page.
2. Note detail/edit page: structured fields, raw-JSON toggle (cheap, do
   early — it's just a read-only `<pre>` of the existing serialized note).
3. Audio player + trim + replace (the most involved single piece — D-S2).
4. New-note creation form with PoS-driven prefill (D-S4).
5. Grammar CRUD routes, then the grammar list/detail/new-rule pages,
   reusing the notes pages' list/filter/sort chrome rather than inventing a
   second pattern.
