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

- [x] 4.1 Manually verify: a substantiv note's fields show as grouped rows on both the new-note and existing-note forms. **Operator confirmed the note-form row grouping itself rendered correctly (originally 3+2; revised to article-alone/2/2 per 4.6 below after further feedback).**
- [ ] 4.2 Manually verify: a substantiv paradigm candidate in the suggestion panel shows the same row grouping. **Operator reported this looked "chaotic, not in a grid" after the 4.5 fix below was already applied — re-revised in 4.6; not yet re-verified in a browser.**
- [ ] 4.3 Manually verify: clicking "Fill" on `sg_def` from one provider and `pl_def` from a different provider both land correctly, independently. **Not verified in this session.**
- [ ] 4.4 Manually verify: adjektiv/verb/adverb inflection fields are visually unchanged from today. **Not verified in this session — code change is additive/conditional on `INFLECTION_ROW_GROUPS[pos]` being present, so other PoS shapes take the unchanged fallback branch by construction.**
- [x] 4.5 Fix (round 1, from operator report "chaotic"): each `.paradigm-row` was a horizontal flex row (label, value, Fill button) with `flex-wrap`, so inside the `.inflection-row` grid, cells wrapped their contents independently and landed at different heights. Restructured `.paradigm-row` to a label-above-value layout (matching `.inflection-field`'s own shape), so every cell in a row is visually uniform regardless of its row's column count.
- [x] 4.6 Fix (round 2, from operator feedback "still ugly" + explicit ask): changed the grouping itself from 3+2 (`article`+`sg_indef`+`sg_def`, then `pl_indef`+`pl_def`) to article-alone-then-two-even-pairs: `[['article'], ['sg_indef', 'sg_def'], ['pl_indef', 'pl_def']]`. No CSS change needed beyond 4.5 — `.inflection-row`'s `grid-auto-columns: 1fr` already renders a single-item group as a full-width row.
