## Context

`INFLECTION_SHAPES` in `ui/ui.js` already defines the correct per-PoS field
order. `renderInflectionFields` renders them as a flat list
(`.inflection-fields { display: flex; flex-direction: column }`), one input
per row. The inflections suggestion panel (`buildInflectionsProviderBlock`)
renders each provider candidate's `paradigm` object the same flat way
(`Object.entries(c.paradigm).map(...)`), and confirmed against smia's
`inflect-api` spec, every provider's `paradigm` keys are already identical
to stabbur's own `INFLECTION_SHAPES` keys (`article`, `sg_indef`, etc.) — no
key translation is needed to match a paradigm cell to a form field.

## Goals / Non-Goals

**Goals:**
- Noun fields render as three visually grouped rows — `article` alone, then
  `sg_indef`/`sg_def`, then `pl_indef`/`pl_def` — matching how an operator
  naturally thinks about the article as its own thing and singular/plural as
  even pairs, in both the note form and the suggestion panel's paradigm
  tables.
- A paradigm cell can be applied directly to its matching form field with one
  click, without losing the existing copy-to-clipboard action (some
  operators may still want to paste elsewhere, e.g. into a different note
  entirely).

**Non-Goals:**
- No row-grouping for `adjektiv`/`verb`/`adverb` — not requested; their
  current single flex-wrapping row stays as-is.
- No automatic/bulk fill across all fields from one provider — "Fill" stays
  a one-cell-at-a-time action, same spirit as the existing copy-only design
  (`smia-enrichment-panel`'s explicit non-goal: providers disagree often
  enough that silent bulk fill is a real correctness risk).
- No change to how paradigm candidates are fetched or matched to a PoS —
  purely a rendering/interaction change on data already flowing today.

## Decisions

### D1 — An explicit `INFLECTION_ROW_GROUPS` map, substantiv-only for now
```js
const INFLECTION_ROW_GROUPS = {
  substantiv: [['article'], ['sg_indef', 'sg_def'], ['pl_indef', 'pl_def']],
};
```
`renderInflectionFields(containerId, pos, values)` looks up
`INFLECTION_ROW_GROUPS[pos]`; if present, renders one `.inflection-row`
grid div per group (a dedicated grid class, not the main form's own
`.field-row`, to avoid clashing with that class's unrelated visibility-
toggling behavior elsewhere in the form), each containing that group's
`.inflection-field` cells — `grid-auto-columns: 1fr` means a single-item
group (`article`) naturally renders as one full-width row, with no special-
casing needed for "a row of one." If absent (every other PoS), falls back to
today's flat single-column rendering unchanged.

Revised once already, from an initial `[['article', 'sg_indef', 'sg_def'],
['pl_indef', 'pl_def']]` (3+2) grouping that operator feedback called "still
chaotic" / uneven — article-alone-then-two-matched-pairs reads more cleanly
than a 3-wide row next to a 2-wide one. Rejected alternative (both times): a
generic "chunk into rows of N" rule — grammatically meaningless chunking
(e.g. splitting `positiv`/`nøytrum`/`flertall`/`komparativ`/`superlativ`
into arbitrary groups) would look organized but carry no actual meaning,
unlike the noun case where article/singular/plural are real linguistic
groupings the operator explicitly named.

### D2 — Paradigm-table rendering shares the same row-group map
`buildInflectionsProviderBlock`'s per-candidate rendering, when
`c.pos === 'substantiv'`, groups its `paradigm-row` cells the same way via
`INFLECTION_ROW_GROUPS`, so a provider's noun paradigm visually lines up
with the note form's own noun fields immediately below/beside it. Any
paradigm key not present in the active group list (unexpected/extra key from
a provider) still renders, appended after the grouped rows, so no data is
ever silently dropped by the grouping logic.

### D3 — "Fill" is a sibling action to the existing copy icon, not a replacement
Each paradigm cell currently renders as a single `.copy-cell` (click →
clipboard). This change adds a small "Fill →" button next to it (not
replacing the click-to-copy behavior, since the suggest panel's standing
requirement is still "the operator decides which provider's form to use per
field," and "copy, then paste wherever" remains valid for e.g. the "new
note, different PoS than expected" edge case). The fill button:
- Is only rendered for a key present in the active note form's current PoS
  shape (`document.querySelector('[data-inflection-field="<key>"]')` must
  exist for the active `prefix`) — if the note's PoS doesn't have that field
  (e.g. a provider mistakenly returns a verb-shaped paradigm while the note
  is `pos=substantiv`), only copy is offered, since there's no field to fill.
- Writes the value directly into the matching `[data-inflection-field]`
  input (dispatching an `input` event, matching the pattern
  `renderIpaCandidate` already uses for the transcription field) and gives
  the same lightweight toast feedback (`enrichToast`) the other "Use"
  interactions already give.
- Does not mark anything "used" exclusively (unlike IPA/TTS's single-value
  `markSuggestUsed`) — each of the five fields can be filled independently
  from different providers' cells, one after another, with no mutual
  exclusivity.

## Risks / Trade-offs

- **[Trade-off]** Hardcoding the row grouping to substantiv only means a
  future ask for adjektiv/verb grouping needs its own follow-up change.
  Accepted — matches what was actually requested, avoids guessing at a
  grouping nobody asked for.

## Migration Plan

- Additive, UI-only. Rollback is reverting the `ui.js`/`ui.css` changes; no
  data or API shape changes anywhere.
