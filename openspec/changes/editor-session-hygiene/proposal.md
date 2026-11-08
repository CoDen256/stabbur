## Why

Three unrelated-looking editor annoyances share one root cause: the editor
treats the form and its suggest panels as page-level furniture that happens
to be reused, rather than as state belonging to one note.

- **The form survives the note.** After saving, `submitNewNote` navigates to
  the created note (`ui/ui.js:988`) but never clears the create form. Coming
  back to "+ New note" shows the previous note's fields, its suggest-control
  queries, and — because `newNoteAudioFromSuggest` is only reset on the save
  path — potentially stale audio intent.
- **Panels stay open with the previous note's candidates.** `openSuggestPanel`
  fills a panel's `innerHTML` and leaves it; nothing closes or empties panels
  when a different note is loaded. The operator sees one note's provider
  results above another note's fields.
- **An edited query can only be re-fired by collapsing and reopening.** Enter
  in the shared query field re-fires (`ui/ui.js:1109`), but there is no
  visible control saying so, and the per-provider `⟳` has the same
  discoverability gap.

Separately, the query-sourcing model introduced by `lemma-first-suggestions`
has not survived use. It routes every kind through `lemma || text`, which
conflates two genuinely different lookups: a paradigm lookup wants the bare
headword, while translation, audio, and transcription want the phrase as
written. The operator's resolution is simpler than the current rule, not
more complex: **`lemma` feeds inflections and nothing else; `text` feeds
everything else.**

That reversal also retires the `"å "`-stripping "From text" button. The
infinitive marker is no longer expected in `text` at all, and smia's own
`norwegian-input` capability now strips a leading `en`/`ei`/`et`/`å` into an
additional query variant at the `/ipa` route (and in the `ordbank` and
`dictcc_api` adapters), so a stray marker is handled upstream for those
paths rather than needing a client-side transform.

## What Changes

- **`lemma` feeds inflections only; `text` feeds everything else.** The
  `lemma || text` default is replaced per kind: `inflections` reads `lemma`,
  while `ipa`, `tts`, and `translations` read `text`. This supersedes
  `lemma-first-suggestions`' central decision.
- **`lemma` is derived reactively from `text`, and the button is removed.**
  The verb-only "From text" button is deleted along with
  `deriveLemmaFromText`. `lemma` is instead kept in sync with the first
  token of `text` as the operator types, and remains freely editable — a
  manual edit stops the syncing for that note, exactly as the suggest
  controls' existing `dirty` flag already works for queries.
- **A new note starts clean.** Saving (or navigating away from) the
  new-note form clears every field, every suggest-control query and its
  `dirty` flag, any pending suggested audio, and the file input.
- **Suggest panels close and empty when a different note is loaded.**
  Panels are collapsed and their contents discarded on note load, so no
  panel ever displays another note's candidates.
- **An explicit "re-run every provider" control on each suggest pill.** A
  visible `⟳` next to the shared query re-fires every provider in that
  panel without collapsing it, making the existing Enter behaviour
  discoverable.
- **Re-running forces a fresh lookup.** smia's lookup cache means a plain
  re-query returns the cached answer, so a re-run after editing a query
  would appear to do nothing. stabbur's proxy therefore forwards a
  force-refresh flag on an explicit re-run. smia accepts `forceRefresh` on
  every kind (`routes/generic.py`'s generic factory default, and explicitly
  in `routes/ipa.py`).

## Capabilities

### Modified Capabilities

- `note-editor`: query sourcing per kind, the removal of the lemma-derive
  action in favour of reactive derivation, new-note form lifecycle, panel
  lifecycle across notes, and the explicit re-run control are all
  requirement-level behaviours.
- `smia-enrichment`: the proxy gains the ability to forward an
  operator-initiated force-refresh. This is a contract change to what
  stabbur sends, so it is recorded rather than left as implementation.

## Impact

- **stabbur UI** (`ui/ui.js`): `defaultSuggestQuery` splits per kind;
  `deriveLemmaFromText`, `wireLemmaSuggestButton`, and
  `updateLemmaSuggestVisibility` are removed; new reactive `text` → `lemma`
  sync with a dirty flag; new `resetCreateForm`; `resetSuggestQueries`
  extended to also close and empty panels; `openSuggestPanel` and the
  per-provider retry gain a force-refresh path.
- **stabbur UI** (`ui/index.html`): the two `*_lemma_suggest_btn` buttons
  are removed; each suggest control gains a `⟳` control.
- **stabbur UI** (`ui/ui.css`): styling for the re-run control.
- **stabbur backend** (`routes/enrich.py`): `post_enrich` forwards a
  `forceRefresh` flag when the client sends one. Still a pass-through — the
  flag originates with the operator, not with stabbur.
- **No schema changes.**
- Sequenced **after** `smia-ipa-multiword-response`, which fixes a live
  regression in the same result-handling code and should land first to
  avoid rebasing it onto this.
