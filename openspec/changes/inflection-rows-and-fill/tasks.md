## 1. Row grouping

- [x] 1.1 `ui/ui.js`: add `INFLECTION_ROW_GROUPS` (substantiv only, per design D1).
- [x] 1.2 `ui/ui.js`: `renderInflectionFields` renders grouped rows when `INFLECTION_ROW_GROUPS[pos]` exists, falling back to the current flat layout otherwise.
- [x] 1.3 `ui/ui.css`: row-group styling, reusing the existing `.field-row` grid pattern.

## 2. Paradigm table grouping

- [x] 2.1 `ui/ui.js`: `buildInflectionsProviderBlock`'s candidate rendering groups a `substantiv` candidate's paradigm cells using the same `INFLECTION_ROW_GROUPS`, appending any ungrouped/unexpected keys after.

## 3. Fill action

- [x] 3.1 `ui/ui.js`: add a "Fill" button next to each paradigm cell's existing copy action.
- [x] 3.2 `ui/ui.js`: Fill button only renders when `[data-inflection-field="<key>"]` exists for the active prefix's current PoS; otherwise only copy is shown.
- [x] 3.3 `ui/ui.js`: Fill handler writes the value into the matching field, dispatches an `input` event, and shows an `enrichToast` confirmation — no `markSuggestUsed` exclusivity (each field fills independently).

## 4. Verification

- [x] 4.1 Manually verify: a substantiv note's fields show as two rows (3 + 2) on both the new-note and existing-note forms. **Operator confirmed the note-form row grouping itself rendered correctly.**
- [ ] 4.2 Manually verify: a substantiv paradigm candidate in the suggestion panel shows the same two-row grouping. **Operator reported this looked "chaotic, not in a grid" — see 4.5 fix below; not re-verified in a browser since.**
- [ ] 4.3 Manually verify: clicking "Fill" on `sg_def` from one provider and `pl_def` from a different provider both land correctly, independently. **Not verified in this session.**
- [ ] 4.4 Manually verify: adjektiv/verb/adverb inflection fields are visually unchanged from today. **Not verified in this session — code change is additive/conditional on `INFLECTION_ROW_GROUPS[pos]` being present, so other PoS shapes take the unchanged fallback branch by construction.**
- [x] 4.5 Fix (from operator report): the paradigm suggestion grid looked chaotic — each `.paradigm-row` was a horizontal flex row (label, value, Fill button) with `flex-wrap`, so inside a 3-wide/2-wide `.inflection-row` grid, cells wrapped their contents independently and landed at different heights. Restructured `.paradigm-row` to a label-above-value layout (matching `.inflection-field`'s own shape), so every cell in a row is visually uniform regardless of its row's column count.
