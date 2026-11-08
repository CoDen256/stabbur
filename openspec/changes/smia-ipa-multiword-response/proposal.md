## Why

smia's `/ipa` changed shape (smia commits `a044ac0`, `8875c03`, archived as
`ipa-multiword` and synced into its `ipa-api` spec). The response is now a
union discriminated on a `mode` field:

- `{provider, mode: "phrase", candidates: [{ipa, variety?}]}` — today's
  shape, returned for a single word and for a multi-word input the provider
  holds as one entry.
- `{provider, mode: "per_word", tokens: [{text, candidates: [...]}], joined?}`
  — returned when a multi-word input has no whole-phrase entry.

**stabbur silently breaks against the second shape.** `buildEnrichProviderRow`'s
result handler (`ui/ui.js:1386`) bails on anything without a non-empty
`body.candidates` array:

```js
if (status !== 200 || !body || !Array.isArray(body.candidates) || body.candidates.length === 0) {
```

A `per_word` response has no `candidates` key at all, so every multi-word
transcription lookup that misses as a phrase renders "no results" — looking
like a provider gap rather than a shape stabbur doesn't understand. This is
a regression the moment the new smia is deployed, not a missing feature, and
it is the reason this change is sequenced ahead of the other note-editor
work in flight.

## What Changes

- **The IPA panel understands `mode`.** `mode: "phrase"` renders exactly as
  today. `mode: "per_word"` renders one sub-row per token, in input order,
  each with that token's own candidates and its own "Use" affordance.
- **A token with no entry is shown, not hidden.** smia guarantees one
  `tokens` entry per token including gaps (`candidates: []`); stabbur shows
  that token as present-but-unresolved rather than dropping it, so the
  operator can see which word is missing.
- **`joined` is offered when present, and never fabricated when absent.**
  smia includes `joined` **if and only if** every token resolved to exactly
  one candidate, and is explicit that its absence "is the signal that
  assembling a phrase transcription requires a choice the system will not
  make on the caller's behalf". stabbur honours that: when `joined` is
  present it is offered as a one-click fill; when absent, stabbur SHALL NOT
  concatenate the tokens itself.
- **`joined` is labelled for what it is.** smia is equally explicit that
  `joined` "SHALL NOT be presented as the phrase's actual pronunciation" —
  it is an assembly of citation forms. stabbur's UI says so rather than
  presenting it identically to a real phrase lookup.
- **No change to variety handling.** smia now merges candidates sharing an
  identical `ipa`, joining their varieties with `/` (e.g. `variety: "e/sw"`).
  `renderIpaCandidate` already renders `c.variety` verbatim (`ui/ui.js:1417`),
  so this passes through correctly with no work. Recorded here so it is not
  re-scheduled as a task.

## Capabilities

### Modified Capabilities

- `note-editor`: how a transcription suggestion panel presents a provider's
  answer is requirement-level behaviour, and it now has two distinct shapes
  rather than one. The "no fabricated join" rule is a correctness constraint
  on the editor, not an implementation detail.

## Impact

- **stabbur UI** (`ui/ui.js`): `buildEnrichProviderRow`'s IPA result branch
  gains `mode` dispatch; new per-word token rendering; `renderIpaCandidate`
  reused unchanged for each token's candidates.
- **stabbur UI** (`ui/ui.css`): styles for the per-word token breakdown and
  the `joined` row.
- **No backend changes.** `routes/enrich.py` passes smia's body through
  unchanged (`smia-enrichment`'s standing pass-through rule), so the new
  shape already reaches the browser intact. No new route, no new proxy
  logic.
- **No schema changes.**
- Does not depend on, and is not depended on by, `bulk-import-anki-csv`
  (concurrent work, confined to `import/` and `scripts/import`).
