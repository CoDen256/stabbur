## 1. Row grouping

- [ ] 1.1 `ui/ui.js`: add `INFLECTION_ROW_GROUPS` (substantiv only, per design D1).
- [ ] 1.2 `ui/ui.js`: `renderInflectionFields` renders grouped rows when `INFLECTION_ROW_GROUPS[pos]` exists, falling back to the current flat layout otherwise.
- [ ] 1.3 `ui/ui.css`: row-group styling, reusing the existing `.field-row` grid pattern.

## 2. Paradigm table grouping

- [ ] 2.1 `ui/ui.js`: `buildInflectionsProviderBlock`'s candidate rendering groups a `substantiv` candidate's paradigm cells using the same `INFLECTION_ROW_GROUPS`, appending any ungrouped/unexpected keys after.

## 3. Fill action

- [ ] 3.1 `ui/ui.js`: add a "Fill" button next to each paradigm cell's existing copy action.
- [ ] 3.2 `ui/ui.js`: Fill button only renders when `[data-inflection-field="<key>"]` exists for the active prefix's current PoS; otherwise only copy is shown.
- [ ] 3.3 `ui/ui.js`: Fill handler writes the value into the matching field, dispatches an `input` event, and shows an `enrichToast` confirmation — no `markSuggestUsed` exclusivity (each field fills independently).

## 4. Verification

- [ ] 4.1 Manually verify: a substantiv note's fields show as two rows (3 + 2) on both the new-note and existing-note forms.
- [ ] 4.2 Manually verify: a substantiv paradigm candidate in the suggestion panel shows the same two-row grouping.
- [ ] 4.3 Manually verify: clicking "Fill" on `sg_def` from one provider and `pl_def` from a different provider both land correctly, independently.
- [ ] 4.4 Manually verify: adjektiv/verb/adverb inflection fields are visually unchanged from today.
