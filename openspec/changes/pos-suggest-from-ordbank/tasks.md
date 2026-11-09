## 1. Whole-paradigm apply

- [ ] 1.1 `ui/ui.js` `buildInflectionsProviderBlock`: add one apply action per candidate, alongside the existing per-cell copy and per-field fill (both of which stay).
- [ ] 1.2 **Order is load-bearing**: set `pos` first via `setPosValue`, then call `updateEditInflectionFields` so the fields exist, then write the forms. Writing forms before the part of speech is set targets fields that are hidden and empty (`ui.js:448` — the block is `display:none` when `INFLECTION_SHAPES[pos]` is undefined).
- [ ] 1.3 Set `pos` **only when the note has none** (design D2). An existing part of speech is never changed by this action.
- [ ] 1.4 Fill only the forms whose key has a matching field for the resulting part of speech; ignore the rest (the existing non-matching-key rule still holds for them).
- [ ] 1.5 A candidate whose provider reported no `pos`, on a note with none, applies nothing — do not invent a part of speech, and do not fill into hidden fields.
- [ ] 1.6 Works on both the new-note form and the existing-note editor (`c_`/`e_` prefixes), per `note-editor`'s existing "panels work on both" requirement.

## 2. Part-of-speech suggest control

- [ ] 2.1 `ui/index.html`: a suggest control beside the part-of-speech field on both forms, reusing the existing combined-control markup rather than new structure (design D4).
- [ ] 2.2 `ui/ui.js`: query defaults to `lemma || text`, matching every other panel since `lemma-first-suggestions`.
- [ ] 2.3 Applying a suggested value **overwrites** the current part of speech (design D2) — this is the deliberate asymmetry with task 1.3.
- [ ] 2.4 Where the note's existing part of speech differs from the reported one, show both before the operator chooses.
- [ ] 2.5 Fires only on opening the control or pressing retry — never on typing (`note-editor`'s existing rule).
- [ ] 2.6 Changing the part of speech via this control re-renders the inflection fields for the new shape, preserving any values whose keys exist in both shapes.

## 3. Word-class mapping

- [ ] 3.1 Map smia's `_pos_for()` fallback tokens: `prep`→`preposisjon`, `konj`→`konjunksjon`, `sbu`→`konjunksjon`. The four main classes already arrive canonical from `_SLOT_MAPS` — do not re-map them.
- [ ] 3.2 `pron`, `det`, `interj`, `symb`, `forkorting` have no canonical equivalent: display the provider's raw answer, offer **no** apply action (design D3).
- [ ] 3.3 Keep the mapping in one place, used by both entry points, so they cannot disagree.
- [ ] 3.4 Assert the mapping's output is always one of `KNOWN_POS_VALUES` (`ui.js:31`) or nothing.

## 4. Verification

- [ ] 4.1 A note with no part of speech: open inflections, apply a candidate — part of speech is set, fields appear, forms land. This is the case that is currently impossible and the reason for the change.
- [ ] 4.2 A note with `substantiv` set and a provider reporting `verb`: applying the paradigm leaves `substantiv` untouched; the disagreement is visible.
- [ ] 4.3 The same note via the part-of-speech suggest control: applying `verb` does replace `substantiv`.
- [ ] 4.4 A word Ordbank reports as `pron`: shown, not offered.
- [ ] 4.5 A word Ordbank reports as `prep`: offered as `preposisjon`.
- [ ] 4.6 **Measure Ordbank's real coverage** of the gap (design's first stated risk): sample 50 of the unresolved single content words (`hallo`, `seks`, `langt`, `unnskyld`, `greide`, `begge`, `seint`, `ni`, `åtte`) and record the hit rate in design.md. Nothing has been queried against the real table yet — if coverage is poor, the change delivers much less than it promises and that should be known rather than assumed.
- [ ] 4.7 A surface form resolving to several lemmas with different parts of speech (D137's `fort`/`fore` hazard) shows multiple candidates rather than picking one.
- [ ] 4.8 Backend regression suite green — this change is UI-only and touches no route, so a diff confined to `ui/` is itself part of the check (same convention as `lemma-first-suggestions`).
