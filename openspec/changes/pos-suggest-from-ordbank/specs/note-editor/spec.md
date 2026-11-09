## ADDED Requirements

### Requirement: The part-of-speech field offers provider-sourced suggestions
The system SHALL provide a suggest control next to the note's part-of-speech
field, following the same combined toggle + live editable shared query
pattern used by the transcription, translations, audio and inflections
controls, defaulting its query to the note's `lemma` and falling back to
`text`. Applying a suggested part of speech SHALL replace whatever value the
field currently holds.

#### Scenario: Suggesting a part of speech for a note that has none
- **WHEN** the operator opens the part-of-speech suggest control on a note
  with no part of speech, and the provider reports one
- **THEN** the reported value is offered, and applying it sets the note's
  part of speech

#### Scenario: Explicitly replacing an existing part of speech
- **WHEN** the note already has a part of speech, and the operator opens the
  part-of-speech suggest control and applies a different reported value
- **THEN** the note's part of speech is replaced with the applied value

#### Scenario: The provider's answer disagrees with the note
- **WHEN** the provider reports a part of speech different from the one the
  note already carries
- **THEN** both are shown, so the operator sees the disagreement before
  choosing

#### Scenario: No lookup without an explicit action
- **WHEN** the operator edits the note's `text` or `lemma`
- **THEN** no part-of-speech lookup is fired until the operator opens the
  control or presses a retry

### Requirement: A reported word class outside the supported set is shown but not offered
The system SHALL display a provider's reported word class even when it has
no equivalent among the parts of speech the system supports, and SHALL NOT
offer to apply a value outside that set.

#### Scenario: A pronoun or determiner
- **WHEN** the provider reports a word class that the system has no
  equivalent for
- **THEN** the reported class is shown as the provider's own answer, with no
  action offered to apply it

#### Scenario: A word class with a direct equivalent
- **WHEN** the provider reports a word class that maps onto one of the
  supported parts of speech
- **THEN** the mapped value is offered for applying

## MODIFIED Requirements

### Requirement: Inflection paradigms are looked up read-only, for manual copy
The system SHALL provide a combined suggest control — the same toggle +
live, editable shared query + progressive-disclosure per-provider overrides
used for transcription/translations/audio — for inflections, positioned
below the note's own inflection fields rather than above them, opening a
panel showing each configured provider's full paradigm as its own table,
with each form individually copyable, and SHALL additionally let the
operator fill a form directly into its matching inflection field on the
note with one click, when that field exists for the note's current part of
speech. The system SHALL additionally offer a single action per candidate
that applies the whole paradigm — setting the note's part of speech when the
note has none, then filling every form that has a matching field — so that a
paradigm is usable on a note whose part of speech is not yet set. That
action SHALL NOT change a part of speech the note already carries. A
paradigm's forms SHALL be ordered the same way the note's own inflection
fields are ordered, regardless of what order a provider's response happens
to list them in. The system SHALL NOT auto-fill the note's inflection fields
from a lookup on its own — every fill remains an explicit operator action.

#### Scenario: Looking up inflections
- **WHEN** the operator opens the inflections suggest control
- **THEN** a panel opens, positioned below the note's inflection fields,
  showing every configured inflections provider's paradigm as a separate
  table, matching the note's current part-of-speech shape where the
  provider's data supports it

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

#### Scenario: Applying a whole paradigm to a note with no part of speech
- **WHEN** the operator applies a provider's whole candidate on a note that
  has no part of speech, and the provider reported one
- **THEN** the note's part of speech is set to the reported value, its
  inflection fields for that part of speech become available, and every
  reported form with a matching field is filled

#### Scenario: Applying a whole paradigm never overrides an existing part of speech
- **WHEN** the operator applies a provider's whole candidate on a note that
  already has a part of speech
- **THEN** the note's part of speech is left exactly as it was, and only the
  forms with matching fields are filled

#### Scenario: A provider reporting no part of speech
- **WHEN** the operator applies a whole candidate whose provider reported no
  part of speech, on a note that has none
- **THEN** no part of speech is invented, and no inflection field is filled,
  because none exists to fill

#### Scenario: Fill is unavailable for a non-matching field
- **WHEN** a provider's paradigm includes a key that has no corresponding
  field for the note's current part of speech
- **THEN** only the copy action is offered for that cell, not a fill action

#### Scenario: Providers disagree
- **WHEN** two providers report different forms for the same paradigm slot
- **THEN** the panel surfaces the disagreement rather than silently picking
  one provider's answer, and filling from one provider does not prevent
  filling a different field from a different provider afterward

#### Scenario: A paradigm's forms follow the note's own field order
- **WHEN** a provider's response lists a verb paradigm's forms in some order
  other than infinitiv/presens/preteritum/perfektum (the note form's own
  order)
- **THEN** the panel still displays them in infinitiv/presens/preteritum/
  perfektum order, not whatever order the provider's response used
