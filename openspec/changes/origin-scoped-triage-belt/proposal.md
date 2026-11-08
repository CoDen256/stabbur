## Why

Reviewing drafts one at a time through the notes browser means a round trip
per note: filter the list, click a row, edit, save, navigate back, find
where you were. For a handful of notes that is fine. For an Anki import of
several thousand — which `bulk-import-anki-csv` is actively producing — it
is the whole job, and the navigation is most of the work.

What the operator wants is a belt: one drafted note on screen at a time,
already prefilled, with three keys underneath — accept, defer, delete — and
the next note arriving without a navigation step.

Two things make this worth building now rather than as a notes-browser
tweak:

- **`note-origin-provenance` landed**, giving every note a positive
  `origin` of `manual`, `capture`, or `import`. Imported notes and
  hand-authored ones need completely different review attention: an import
  arrives in bulk with empty fields and needs prefilling and a fast yes/no,
  while a hand-authored draft is something the operator already thought
  about. Mixing them in one queue makes both worse. So the belt is scoped
  to one origin at a time.
- **`operator-settings` gives primary providers somewhere to live**, which
  is what makes "already prefilled" possible without choosing a provider
  per field per note.

## What Changes

- **A triage capability**: a queue of drafted notes reviewed one at a time,
  as a new tab alongside the notes browser. The existing editor is
  unchanged and remains the way to open any single note — the belt is an
  additional surface, not a replacement.
- **The queue is scoped to one origin.** The operator picks which origin
  they are triaging, giving a separate belt for imported notes and for
  hand-authored ones, each with its own remaining count.
- **Three verdicts, always in the same place**: accept (mark ready and
  advance), send to back (keep edits, requeue at the end), and delete.
  Plus skip, which advances without recording anything.
- **Prefill from primary providers.** Fields still empty are filled from
  the operator's primary provider for each kind, walking down their
  configured order when one has no entry. A field the operator has touched,
  or that arrived with the note, is never overwritten.
- **Prefill timing is configurable**: automatically on opening a note, or
  only when the operator presses a fill control. Both are useful — automatic
  is faster for a bulk import, on-demand avoids spending lookups on notes
  that will be deleted on sight.
- **Suggestion panels start closed.** The prefilled values are shown in the
  fields themselves; provider rows stay out of the way until the operator
  wants to compare or re-run.
- **Provenance is shown per prefilled field**, naming which provider
  supplied the value — required by `operator-settings`' carve-out to the
  no-fallback rule, and useful on its own when reviewing at speed.
- **Audio capture accepts any pasted link, independent of a provider row.**
  stabbur's two paste-back endpoints are named per provider
  (`/api/enrich/manual-link/forvo`, `/api/enrich/manual-link/filmot`) but
  are functionally "fetch a direct audio URL" and "clip a YouTube URL at a
  timecode" — neither contacts Forvo or filmot. A single paste box that
  discriminates on the link itself is a better fit for what the code
  already does, and removes the need to pick a provider row before pasting.

The agreed visual design for all of this is
`assets/triage-belt-mock.html` in this change, also published at
<https://claude.ai/artifact/QAbEkkFhG2vu8EkVdw3fF4>. The in-tree copy is
the source of truth, following how `lemma-first-suggestions` and
`smia-enrichment-panel` treated their own mockups.

## Capabilities

### Added Capabilities

- `note-triage`: the queue, its origin scoping, the verdicts, deferral
  semantics, and prefill-on-review. New capability — reviewing a queue is a
  different activity from editing a note, and the existing `note-editor`
  and `notes-browser` capabilities describe neither.

### Modified Capabilities

- `manual-link-audio-capture`: capture becomes link-shaped rather than
  provider-shaped. The existing per-provider paste-back rows keep working;
  what changes is that pasting is no longer tied to having chosen a
  provider first.

## Impact

- **stabbur backend** (`routes/notes.py`): the authoring list endpoint
  already supports `status`, `origin`, and `sort`, so the queue is largely
  expressible with what exists. A deferral mechanism is the one piece that
  is not — see design.
- **stabbur backend** (`routes/enrich.py`): a link-shaped audio capture
  endpoint, reusing the existing `_validate_fetch_url` and
  `_parse_youtube_timecode` helpers. The two provider-named routes remain
  as thin aliases.
- **stabbur UI**: a new triage route, page, and rail entry; the belt
  layout; the verdict bar and its keyboard bindings; prefill orchestration
  in the browser as N ordinary pass-through lookups.
- **Schema**: possibly none — see the design's deferral decision, which
  prefers reusing existing ordering over a new column.
- **Depends on** `operator-settings` (primary providers, prefill timing),
  and reads better after `editor-session-hygiene` and
  `smia-ipa-multiword-response`, since the belt inherits the editor's
  query sourcing and response handling.
- **Coordinate with `bulk-import-anki-csv`**, which is in flight and
  produces exactly the `origin=import` drafts this belt consumes. No file
  overlap — that change is confined to `import/` and `scripts/import` —
  but it is the source of this one's primary workload.
