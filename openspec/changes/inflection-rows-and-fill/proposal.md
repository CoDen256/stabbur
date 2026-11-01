## Why

Two small frictions in the inflection UI: the per-PoS field order already
matches the operator's preferred reading order
(`article, sg_indef, sg_def, pl_indef, pl_def` for nouns, etc. —
`INFLECTION_SHAPES` in `ui/ui.js`), but every field stacks one-per-row
regardless of shape, which wastes vertical space for a noun's naturally
paired singular/plural forms. Separately, the inflections suggestion panel
is strictly copy-only (`buildInflectionsProviderBlock`): a provider's
paradigm cell can only be copied to the clipboard, then manually pasted into
the matching note field — a "fill" action that writes it directly would save
that round trip without changing the panel's read-only-by-design nature (the
operator still explicitly chooses which provider's form to apply, per field).

## What Changes

- Noun (`substantiv`) inflection fields render as three rows instead of five
  stacked rows: `article` alone on its own row, then `sg_indef`/`sg_def`
  together, then `pl_indef`/`pl_def` together. This applies both to the note
  form's own inflection fields and to each paradigm candidate's layout in the
  suggestion panel, so the two stay visually aligned. (Revised from an
  initial 3+2 grouping — `article`+`sg_indef`+`sg_def` together — after
  operator feedback that it still read as uneven; article-alone-then-two-
  even-pairs reads more cleanly.)
- Other PoS shapes (`adjektiv`, `verb`, `adverb`) keep their current
  single-row/wrapping layout — no row-grouping request was made for them,
  and inventing one isn't part of this change.
- Each paradigm cell in the inflections suggestion panel gains a "Fill"
  action alongside the existing click-to-copy behavior: clicking it writes
  that value directly into the corresponding inflection field on the note
  form (matched by field key), still one explicit click per field, still the
  operator's choice per field — this does not reintroduce bulk auto-fill
  (the `smia-enrichment-panel` design's explicit non-goal), since nothing
  fires without that per-cell click.

## Capabilities

### Modified Capabilities
- `note-editor`: the inflection-fields layout requirement gains the
  substantiv row-grouping; the "Inflection paradigms are looked up
  read-only, for manual copy" requirement is extended to also allow a direct
  per-field fill action (still per-field, still operator-triggered, still no
  automatic cross-provider resolution).

## Impact

- `stabbur` UI (`ui/ui.js`): `renderInflectionFields` needs PoS-aware row
  grouping instead of one flat list; `buildInflectionsProviderBlock`'s
  paradigm-row rendering needs the same grouping for substantiv candidates,
  plus a "Fill" button per cell wired to `e_`/`c_`-prefixed inflection
  field inputs.
- `stabbur` UI (`ui/ui.css`): new row-group styling (likely reusing the
  existing `.field-row` grid pattern already used elsewhere in the form).
- No backend changes — this is pure note-editor UI.
