## 1. Lemma-first query sourcing

- [x] 1.1 `ui/ui.js`: `openSuggestPanel`'s generic (ipa/tts) branch — change `defaultQuery` from `suggestFieldValue(prefix, 'text')` to `suggestFieldValue(prefix, 'lemma') || suggestFieldValue(prefix, 'text')`.
- [x] 1.2 `ui/ui.js`: `buildTranslationsSuggestPanel` — same change to its `defaultQuery`.
- [x] 1.3 Confirm the `inflections` branch is unchanged (already correct).

## 2. "From text" lemma-suggest button

- [x] 2.1 `ui/index.html`: add a "From text" button next to the Lemma field on both the new-note (`c_lemma_field`) and existing-note (`e_lemma_field`) forms, hidden by default.
- [x] 2.2 `ui/ui.js`: add `deriveLemmaFromText(text)` — trims and strips a leading `/^å\s+/i`.
- [x] 2.3 `ui/ui.js`: wire the button's click handler per prefix — sets the lemma input's value, dispatches `input`, no provider call involved.
- [x] 2.4 `ui/ui.js`: show/hide the button based on `getPosValue(...) === 'verb'`, computed inside each form's existing `wirePosCustomToggle` callback and on initial render (`renderNoteDetail`, `renderNewNote`) — not a new parallel listener.

## 3. Combined suggest control

- [x] 3.1 `ui/index.html`: restructure each suggest-toggle button (`e_ipa_suggest`/`c_ipa_suggest`, `e_tts_suggest`/`c_tts_suggest`, `e_translations_suggest`/`c_translations_suggest` toggles) into the pill markup from the mockup — toggle button + divider + query input, per design D3.
- [x] 3.2 `ui/ui.css`: `.suggest-control`, `.suggest-toggle`, `.suggest-control-divider`, `.suggest-query` styles, matching `assets/lemma-first-suggestions-mock.html`.
- [x] 3.3 `ui/ui.js`: live-update each suggest control's query field and toggle label (provider count) — wire `input` listeners on `lemma`/`text` per prefix, and extend the PoS-change hooks (task 2.4's same hook point) since PoS changes can affect lemma relevance.
- [x] 3.4 `ui/ui.js`: `openSuggestPanel` reads its query from the control's current input value (not a freshly recomputed default) when firing — so an edit made before opening is respected.
- [x] 3.5 `ui/ui.js`: wire `Enter` in the shared query field to open (if closed) and (re-)fire every provider in that panel, per design D4. No fire-on-keystroke.

## 4. Progressive disclosure for per-provider overrides

- [x] 4.1 `ui/ui.js`: `buildEnrichProviderRow` (ipa/tts/translations rows) — replace the always-visible `.provider-query` input with a collapsed-by-default override, revealed via a small ✎ button per row.
- [x] 4.2 `ui/ui.css`: `.provider-edit-btn`, `.provider-own-query` (hidden/`.revealed`) styles, matching the mockup.
- [x] 4.3 `ui/ui.js`: revealed override starts empty (placeholder only); retry uses the override's value if revealed and non-empty, else the panel's shared query value (design D5).
- [x] 4.4 ~~Confirm the inflections panel (`buildInflectionsProviderBlock`) and the stt panel (`buildSttProviderBlock`) are unchanged — neither adopts the combined control or progressive disclosure (non-goals).~~ **Superseded in round 2 below**: the operator asked for inflections to get the exact same mechanism after seeing it elsewhere — the "read-only, no pill" non-goal didn't survive contact with the actual UI. stt is still unchanged (one transcription per provider, no candidates list, nothing to apply this to).

## 5. Verification

- [ ] 5.1 Manually verify: a verb note with `text="å spise"` shows "From text" next to Lemma; clicking it sets `lemma` to `"spise"`. **Not verified in this session — no running backend/browser available; logic reviewed directly in the diff (`deriveLemmaFromText("å spise")` → `"spise"`).**
- [ ] 5.2 Manually verify: switching PoS away from `verb` hides the "From text" button; switching back to `verb` shows it again. **Not verified in this session.**
- [ ] 5.3 Manually verify: with `lemma` set, every IPA/TTS/translations suggest control shows and queries the lemma, not the text. **Not verified in this session.**
- [ ] 5.4 Manually verify: editing a suggest control's query field and pressing Enter while the panel is closed opens it and fires with the edited value. **Not verified in this session.**
- [ ] 5.5 Manually verify: a provider row's override is hidden until the ✎ is clicked, starts empty, and retrying it only affects that row. **Not verified in this session.**
- [ ] 5.6 Manually verify: the audio panel's suggest control fits and reads cleanly in the narrow sidebar column (not just the wider main-column fields). **Not verified in this session.**

**Backend regression check**: full existing backend test suite (69/69) re-run against a real throwaway Postgres container after this change — unaffected, as expected for a UI-only change (`git diff --stat` touches only `ui/index.html`, `ui/ui.js`, `ui/ui.css`). No frontend test suite exists in this repo to automate 5.1-5.6.

## 6. Round 2 (operator feedback after first look)

- [x] 6.1 Inflections gets the exact same combined-pill + progressive-disclosure mechanism as ipa/tts/translations (reversing 4.4's original non-goal), with the pill relocated *below* `e_inflections_fields`/`c_inflections_fields` (the to-be-filled fields) rather than above them in a label-row button. `buildInflectionsProviderBlock` rewritten to match `buildEnrichProviderRow`'s row shape (✎ reveals an empty per-row override, retry falls back to the shared query); `openSuggestPanel`'s inflections branch now reads from the control via `suggestControlQueryValue` instead of `defaultSuggestQuery`.
- [x] 6.2 Fixed (reported live): a verb paradigm's fields rendered in whatever order the provider's JSON happened to use (`infinitiv, perfektum, presens, preteritum`), not the note form's own order. Added `orderedParadigmEntries(pos, paradigm)`, ordering by `INFLECTION_SHAPES[pos]` with any unexpected key appended after; used in both the grouped (substantiv) and flat (verb/adjektiv/adverb) rendering paths.
- [x] 6.3 TTS candidates (both forms) gain an inline `<audio controls preload="none">` preview — listen before clicking "Use", not just after. New stabbur route `GET /api/enrich/tts/preview/<sha256>` proxies smia's cached bytes through without storing anything (unlike `tts/use`), and is auth-exempt (added to `auth.py`'s exemption list alongside `/blob/`) since a plain `<audio src>` can't carry a bearer header.
- [x] 6.4 New-note form: the "will attach on save" note for a chosen TTS suggestion now also shows an `<audio controls>` player (pointed at `/blob/<sha256>`, already a real stabbur blob at that point) — previously there was no way to hear what you'd picked until after saving the note.
- [x] 6.5 Edit form's Audio sidebar panel reordered: heading → selected-audio player (+ trim/preview-trim) → suggest pill → provider panel — the player used to sit *below* the pill; now it's directly under the heading, above the pill, per the operator's explicit ordering ask.
- [x] 6.6 The manual "Replace audio" upload control is restyled to look like one more provider card (`.provider-row` styling, labeled "Manual upload", button relabeled "Use" to match every candidate's "Use" button) instead of a visually distinct form field. Kept as a static element outside the dynamic `.suggest-panel` (which gets wiped and rebuilt on every open/re-fire) rather than injected into the panel itself, to avoid it being destroyed on refire — same file-input/button IDs and click handler as before, restyled only.

**Backend regression check (round 2)**: full suite re-run against a real throwaway Postgres container: 71/71 (69 prior + 2 new for the preview route, happy-path and failure-surfacing).
