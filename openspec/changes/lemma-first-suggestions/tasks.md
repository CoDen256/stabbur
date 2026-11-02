## 1. Lemma-first query sourcing

- [ ] 1.1 `ui/ui.js`: `openSuggestPanel`'s generic (ipa/tts) branch — change `defaultQuery` from `suggestFieldValue(prefix, 'text')` to `suggestFieldValue(prefix, 'lemma') || suggestFieldValue(prefix, 'text')`.
- [ ] 1.2 `ui/ui.js`: `buildTranslationsSuggestPanel` — same change to its `defaultQuery`.
- [ ] 1.3 Confirm the `inflections` branch is unchanged (already correct).

## 2. "From text" lemma-suggest button

- [ ] 2.1 `ui/index.html`: add a "From text" button next to the Lemma field on both the new-note (`c_lemma_field`) and existing-note (`e_lemma_field`) forms, hidden by default.
- [ ] 2.2 `ui/ui.js`: add `deriveLemmaFromText(text)` — trims and strips a leading `/^å\s+/i`.
- [ ] 2.3 `ui/ui.js`: wire the button's click handler per prefix — sets the lemma input's value, dispatches `input`, no provider call involved.
- [ ] 2.4 `ui/ui.js`: show/hide the button based on `getPosValue(...) === 'verb'`, computed inside each form's existing `wirePosCustomToggle` callback and on initial render (`renderNoteDetail`, `renderNewNote`) — not a new parallel listener.

## 3. Combined suggest control

- [ ] 3.1 `ui/index.html`: restructure each suggest-toggle button (`e_ipa_suggest`/`c_ipa_suggest`, `e_tts_suggest`/`c_tts_suggest`, `e_translations_suggest`/`c_translations_suggest` toggles) into the pill markup from the mockup — toggle button + divider + query input, per design D3.
- [ ] 3.2 `ui/ui.css`: `.suggest-control`, `.suggest-toggle`, `.suggest-control-divider`, `.suggest-query` styles, matching `assets/lemma-first-suggestions-mock.html`.
- [ ] 3.3 `ui/ui.js`: live-update each suggest control's query field and toggle label (provider count) — wire `input` listeners on `lemma`/`text` per prefix, and extend the PoS-change hooks (task 2.4's same hook point) since PoS changes can affect lemma relevance.
- [ ] 3.4 `ui/ui.js`: `openSuggestPanel` reads its query from the control's current input value (not a freshly recomputed default) when firing — so an edit made before opening is respected.
- [ ] 3.5 `ui/ui.js`: wire `Enter` in the shared query field to open (if closed) and (re-)fire every provider in that panel, per design D4. No fire-on-keystroke.

## 4. Progressive disclosure for per-provider overrides

- [ ] 4.1 `ui/ui.js`: `buildEnrichProviderRow` (ipa/tts/translations rows) — replace the always-visible `.provider-query` input with a collapsed-by-default override, revealed via a small ✎ button per row.
- [ ] 4.2 `ui/ui.css`: `.provider-edit-btn`, `.provider-own-query` (hidden/`.revealed`) styles, matching the mockup.
- [ ] 4.3 `ui/ui.js`: revealed override starts empty (placeholder only); retry uses the override's value if revealed and non-empty, else the panel's shared query value (design D5).
- [ ] 4.4 Confirm the inflections panel (`buildInflectionsProviderBlock`) and the stt panel (`buildSttProviderBlock`) are unchanged — neither adopts the combined control or progressive disclosure (non-goals).

## 5. Verification

- [ ] 5.1 Manually verify: a verb note with `text="å spise"` shows "From text" next to Lemma; clicking it sets `lemma` to `"spise"`.
- [ ] 5.2 Manually verify: switching PoS away from `verb` hides the "From text" button; switching back to `verb` shows it again.
- [ ] 5.3 Manually verify: with `lemma` set, every IPA/TTS/translations suggest control shows and queries the lemma, not the text.
- [ ] 5.4 Manually verify: editing a suggest control's query field and pressing Enter while the panel is closed opens it and fires with the edited value.
- [ ] 5.5 Manually verify: a provider row's override is hidden until the ✎ is clicked, starts empty, and retrying it only affects that row.
- [ ] 5.6 Manually verify: the audio panel's suggest control fits and reads cleanly in the narrow sidebar column (not just the wider main-column fields).
