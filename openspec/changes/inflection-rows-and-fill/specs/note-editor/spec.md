## ADDED Requirements

### Requirement: Noun inflection fields are grouped by singular/plural
The system SHALL render a `substantiv` note's inflection fields as two
grouped rows — `article`, `sg_indef`, `sg_def` together on one row, and
`pl_indef`, `pl_def` together on a second row — rather than one field per
row. This grouping SHALL apply identically wherever the noun's inflection
fields are shown: the note form itself, and any suggestion-panel paradigm
table for a `substantiv` candidate.

#### Scenario: Viewing a noun's inflection fields on the note form
- **WHEN** the operator is editing or creating a `pos=substantiv` note
- **THEN** `article`, `sg_indef`, `sg_def` appear together on one row, and
  `pl_indef`, `pl_def` appear together on a second row

#### Scenario: Viewing a noun paradigm candidate in the suggestion panel
- **WHEN** a provider's inflection paradigm for a `substantiv` candidate is
  shown in the suggestion panel
- **THEN** its paradigm cells are grouped into the same two rows as the note
  form's own noun fields

## MODIFIED Requirements

### Requirement: Inflection paradigms are looked up read-only, for manual copy
The system SHALL provide a single inflections lookup panel showing each
configured provider's full paradigm as its own table, with each form
individually copyable, and SHALL additionally let the operator fill a form
directly into its matching inflection field on the note with one click, when
that field exists for the note's current part of speech. The system SHALL
NOT auto-fill the note's inflection fields from a lookup on its own — every
fill remains an explicit, per-field operator action.

#### Scenario: Looking up inflections
- **WHEN** the operator clicks "Look up paradigm"
- **THEN** one panel opens showing every configured inflections provider's
  paradigm as a separate table, matching the note's current part-of-speech
  shape where the provider's data supports it

#### Scenario: Copying a form
- **WHEN** the operator clicks a form's copy action in a provider's paradigm
  table
- **THEN** that form is copied for pasting anywhere; the note's inflection
  fields are not modified automatically

#### Scenario: Filling a form directly into its field
- **WHEN** the operator clicks a form's "Fill" action in a provider's
  paradigm table, and the note's current part-of-speech has a matching
  inflection field for that paradigm key
- **THEN** that field on the note form is set to the provider's value
  immediately, without affecting any other inflection field

#### Scenario: Fill is unavailable for a non-matching field
- **WHEN** a provider's paradigm includes a key that has no corresponding
  field for the note's current part of speech
- **THEN** only the copy action is offered for that cell, not a fill action

#### Scenario: Providers disagree
- **WHEN** two providers report different forms for the same paradigm slot
- **THEN** the panel surfaces the disagreement rather than silently picking
  one provider's answer, and filling from one provider does not prevent
  filling a different field from a different provider afterward
