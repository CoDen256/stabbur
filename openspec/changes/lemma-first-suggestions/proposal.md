## Why

Every suggestion panel except inflections defaults its query to the note's
`text` field. For a verb note, `text` is typically the full infinitive
phrase (`"å spise"`), while `lemma` holds the bare form (`"spise"`) —
inflections already resolved this (`suggestFieldValue(prefix, 'lemma') ||
suggestFieldValue(prefix, 'text')`), but IPA, TTS, and translations did not,
so those three keep sending the "å "-prefixed phrase to every provider.
Separately, there's no way to derive `lemma` from `text` without typing it
by hand, and no visibility — before or after opening a panel — into what
query a "Suggest" control is actually about to run, or an easy way to change
it for every provider in that panel at once.

## What Changes

- **Lemma-first suggestion queries**: IPA, TTS, and translations suggestion
  panels adopt the same `lemma || text` default inflections already uses.
  Since `lemma` is empty/hidden for every non-`word` type, this requires no
  type check — the existing fallback already does the right thing.
- **"From text" lemma-suggest button**: a small button next to the Lemma
  field, visible only when `pos = verb`, that fills `lemma` from `text` with
  the leading Norwegian infinitive marker (`"å "`) stripped. A client-side
  text transform, not a provider lookup.
- **Combined suggest control**: each "Suggest" toggle merges with a live,
  editable query field into one pill-shaped control (mockup:
  `assets/lemma-first-suggestions-mock.html`) — the query is visible
  *before* the panel is even opened, defaults to `lemma || text`, and
  editing it re-fires every provider in that panel together. This replaces
  today's per-provider-only editable inputs as the primary way to change the
  query.
- **Progressive disclosure for per-provider overrides**: each provider row
  keeps the ability to run on a different input than the shared query (e.g.
  retry one provider against the lemma while the rest keep the original
  result), but that per-row input is hidden by default behind a small edit
  (✎) affordance — revealed only when clicked, so the common case (every
  provider sharing one query) stays visually calm.
- Applies uniformly to every suggestion panel kind that currently has
  per-provider rows: `ipa`, `tts`, `translations`. The read-only inflections
  panel and the `stt` panel (single transcription per provider, not a
  candidate list) are visually/structurally different enough to be
  considered separately — see Design for the call on whether they adopt the
  same control.

## Capabilities

### Modified Capabilities
- `note-editor`: suggestion query sourcing (lemma-first), the "From text"
  lemma-suggest action, and the combined suggest-control/progressive-
  disclosure interaction model are all requirement-level changes to how
  suggestions are driven, not just internal implementation.

## Impact

- **stabbur UI** (`ui/ui.js`): `buildEnrichProviderRow`, `buildTranslationsSuggestPanel`,
  and `openSuggestPanel`'s ipa/tts branches change their default-query
  source; new live-updating button-label logic wired to `lemma`/`text`
  input events on both `c_`/`e_` prefixed forms; new "From text" handler;
  per-provider query inputs become hidden-by-default with a reveal toggle.
- **stabbur UI** (`ui/index.html`, `ui/ui.css`): new lemma-suggest button
  markup (verb-conditional visibility); suggest-toggle buttons restructured
  into the combined pill control; provider-row markup gains the edit-reveal
  affordance.
- No backend changes — this is pure note-editor UI, same enrichment routes,
  same request/response shapes.
- No schema changes.
