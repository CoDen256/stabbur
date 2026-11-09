## 1. Bug fixes (no schema change)

- [ ] 1.1 `ui/ui.js` `renderTtsCandidate`: fix the stale guard `if (prefix !== 'e' && prefix !== 'c') return;` in the "Use" click handler so it also admits `'t'` — `attachAudioToNote` already has a complete, working `prefix === 't'` branch; only this one entry point blocks it.
- [ ] 1.2 Verify live on triage: open the audio suggest panel on a triage card, click "Use" on a tts candidate, confirm it attaches (provenance badge `t_audio_src` updates, `triageStagedAudio` is set) the same way manual upload/link-capture already do.
- [ ] 1.3 `ui/ui.css`: give `.candidate-text` `min-width: 0; overflow-x: auto; white-space: nowrap;` (same idiom as `.paradigm-row-value .copy-cell`, but scrollable rather than ellipsis-truncated — a pronunciation variant string needs to stay fully readable). Confirm `.use-btn` stays `flex: none` (already true) so it stays pinned at a fixed width regardless of the text's length.
- [ ] 1.4 Verify live: open the IPA suggest panel on a word whose provider answer is a long `/`-joined multi-variant string (or synthesize one via a temporary test value if none is available live) and confirm the panel/row no longer widens — the long value scrolls within its own space instead.
- [ ] 1.5 Verify the same fix benefits `.ipa-joined-row`'s own candidate text and the translations panel's `.candidate-text`, since both reuse the same class — no separate CSS needed for either.

## 2. Shared article-stripping for the audio query

- [ ] 2.1 `ui/ui.js` `defaultSuggestQuery`: change the `tts` case (currently falling through to the generic `return suggestFieldValue(prefix, 'text');`) to run through the same transform `examples` already uses (`deriveExamplesQuery`), applied to the lemma-or-text value per the existing "query defaults to lemma, falls back to text" rule — do not special-case `tts` as reading `text` only.
- [ ] 2.2 Confirm `inflections`/`pos`'s own query derivation is untouched — only `tts`'s branch changes.
- [ ] 2.3 Verify live: a note whose `lemma`/`text` begins with a bare `en`/`et`/`ei`/`å` token (e.g. `en bil`) opens the audio suggest control with the article already stripped from the query shown in the shared query field.

## 3. Triage: explicit Save action

- [ ] 3.1 `ui/index.html`: add a "Save" button to triage's verdict bar, alongside Accept/Send to back/Skip/Delete, following the existing button markup/classes in that bar.
- [ ] 3.2 `ui/ui.js`: wire the new button to call `saveTriageEdits()` directly — no new payload shape, no status change, no queue advance. Show a toast on success (`enrichToast`) matching the convention other triage actions already use for a non-obvious outcome.
- [ ] 3.3 Add `m` to `TRIAGE_KEY_BINDINGS`, pointed at the new button's id, following the existing single-letter, far-from-delete binding convention.
- [ ] 3.4 Verify live: edit a few fields on a triage card without accepting/skipping/sending back, press Save (or `m`), reload the triage queue (or navigate away and back), confirm the edits persisted and neither `status` nor the queue position changed.

## 4. Operator setting: triage navigation autosave vs. manual

- [ ] 4.1 `db/models.py`: add `SETTINGS_TRIAGE_NAVIGATE_SAVE_MODES = ("autosave", "manual")`, a new nullable `triage_navigate_save: Mapped[str | None]` column on `Settings`, and a matching `CheckConstraint` (`ck_settings_triage_navigate_save`), following `prefill_timing`'s exact shape.
- [ ] 4.2 New Alembic migration (`alembic revision`, chained onto the current head) adding the column and check constraint, with a `downgrade()` that drops both — mirrors `a1c3f7e9b2d4_triage_belt_prefill_timing.py`.
- [ ] 4.3 `settings_store.py`: add `DEFAULT_TRIAGE_NAVIGATE_SAVE = "autosave"` and the corresponding `TRIAGE_NAVIGATE_SAVE_MODES` tuple; include `triage_navigate_save` in `read_scalars`' returned dict (default-applied, same `or DEFAULT_...` idiom) and in the scalar-update function.
- [ ] 4.4 `routes/settings.py`: add `triage_navigate_save` to `ALLOWED_SETTINGS_KEYS` and validate it's one of `settings_store.TRIAGE_NAVIGATE_SAVE_MODES` when present in a PATCH body, following the `prefill_timing` validation exactly.
- [ ] 4.5 `ui/index.html`: add a new `sgroup`/`sitem` to the settings page (same shape as "Triage prefilling") with a segmented control (`autosave` / `manual`) for this preference.
- [ ] 4.6 `ui/ui.js` `renderSettings`/`wireSettingsScalarControls`: render and wire the new segmented control the same way `settingsPrefillTimingSeg` is, PATCHing `{ triage_navigate_save: ... }` on click.
- [ ] 4.7 Backend test coverage: a settings round-trip test confirming the new key defaults to `autosave`, accepts both valid values, and rejects an invalid one — same shape as the existing `prefill_timing` test(s).

## 5. Triage: Send to back / Skip / Go to previous respect the new preference

- [ ] 5.1 `ui/ui.js`: fetch the resolved `triage_navigate_save` setting (via the existing `fetchSettings()` cache) at the point Send to back, Skip, and Go to previous are triggered.
- [ ] 5.2 Send to back: unchanged when `autosave` (already calls `saveTriageEdits()` first); when `manual`, skip the save call entirely and go straight to re-queuing, exactly like Skip does today.
- [ ] 5.3 Skip: when `autosave`, call `saveTriageEdits()` before advancing (new behavior); when `manual`, unchanged (advance only).
- [ ] 5.4 Go to previous (`goToPreviousTriageNote`): when `autosave`, save the note being left (the current `currentTriageNote`) before popping the history stack and navigating back; when `manual`, unchanged. This is additive to the existing undo-stack bookkeeping, not a replacement for it.
- [ ] 5.5 Verify live, both settings values: edit a field, Skip — confirm persisted under autosave and discarded under manual; edit a field, Go to previous — same two checks; confirm Send to back's existing behavior under `autosave` is unchanged, and confirm it now also goes edit-discarding under `manual`.

## 6. Similar-notes: show actual field values, not just presence

- [ ] 6.1 `routes/notes.py` `_serialize_similar_match`: add the actual field values (`translations`, `context_text`, `inflections`, `transcription`, `audio_blob`) to the returned dict, alongside the existing `has_*` booleans (both stay — existing UI logic branches on the booleans for which take-buttons to render at all).
- [ ] 6.2 Backend test coverage: a similar-notes test asserting the new value fields are present and correct for a match that has them, and correctly absent/empty for one that doesn't — extends the existing `similar-notes-merge` test coverage rather than replacing it.
- [ ] 6.3 `ui/ui.js` `similarNoteRowHtml`: render each available field's actual value next to its "Take" button (translations as lang:text pairs, context_text as its own line, inflections as its existing paradigm-row shape or a compact key:value list, transcription as plain text).
- [ ] 6.4 Audio: render a preview control using the existing `buildAudioPreviewButton(url)` helper, pointed at `${API_BASE}/blob/<sha256>` (the existing auth-exempt blob route — no new endpoint), next to the "Take audio" button.
- [ ] 6.5 Verify live: open a note's editor (or a triage card) with at least one related note that has translations, context, inflections, transcription, and audio — confirm every field's actual value is visible and audio is previewable, and that taking a field still works exactly as before (the existing take/merge-bar/commit mechanism is unchanged).

## 7. Final checks

- [ ] 7.1 Backend regression suite green (`pytest`).
- [ ] 7.2 `node --check ui/ui.js`.
- [ ] 7.3 Manual walkthrough of all five items together on a live stack (docker compose), covering at minimum: triage audio Use, a long-IPA-variant panel, triage Save + key `m`, both navigate-save settings values across Skip/Send to back/Go to previous, and a similar-notes row showing real content with a working audio preview.
