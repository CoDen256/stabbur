## ADDED Requirements

### Requirement: Part of speech is written in the canonical vocabulary
The system SHALL write a note's part of speech using only the canonical
values the rest of the ecosystem recognises, and SHALL NOT pass a source's
own part-of-speech vocabulary through unchanged.

#### Scenario: A source labelling parts of speech in another language
- **WHEN** a source labels a word with a part-of-speech term from a
  different vocabulary than the canonical one
- **THEN** the note is written with the canonical equivalent, not the
  source's term

#### Scenario: A source term that coincides with a canonical one
- **WHEN** a source's term happens to be spelled identically to a canonical
  value
- **THEN** it is still resolved through the mapping rather than relied upon
  to coincide

### Requirement: A source part-of-speech value with no canonical equivalent resolves to none
The system SHALL leave the part of speech unset when a source's value has no
canonical equivalent, and SHALL NOT substitute the closest-looking canonical
value.

#### Scenario: A source category outside the canonical set
- **WHEN** a source labels a word with a category that has no canonical
  equivalent
- **THEN** that label contributes no part of speech, and the remaining
  signals are used instead

#### Scenario: No signal resolves a part of speech
- **WHEN** no available signal resolves a word note's part of speech
- **THEN** it is left unset and reported as unresolved, rather than being
  given a default

### Requirement: Part of speech is inferred from the inflection shape in preference to any other signal
The system SHALL infer a word note's part of speech from the shape of its
inflection data where that data is present, in preference to the source's
own label, the note's text, or its translations.

#### Scenario: Inflection data identifying a noun
- **WHEN** a note's inflection data carries keys belonging only to the noun
  shape
- **THEN** its part of speech is the noun value, regardless of what the
  source labelled it

#### Scenario: Inflection shape disagreeing with the source label
- **WHEN** the inflection shape and the source's own label imply different
  parts of speech
- **THEN** the inflection shape decides

#### Scenario: No inflection data present
- **WHEN** a note has no inflection data
- **THEN** the remaining signals are consulted in order of decreasing
  reliability

### Requirement: Disagreeing part-of-speech signals are recorded as a conflict
The system SHALL record a conflict when two signals imply different parts of
speech, alongside the value it selected, using the same mechanism as
cross-source field conflicts.

#### Scenario: Two signals disagreeing
- **WHEN** one signal implies a verb and another implies a noun for the same
  note
- **THEN** the higher-precedence signal's value is applied and the
  disagreement is recorded so the operator sees it during review

### Requirement: Only lexical-item notes carry a part of speech
The system SHALL NOT assign a part of speech to notes that are not single
lexical items, because those are routed by note type rather than by part of
speech.

#### Scenario: A sentence-shaped note
- **WHEN** a note's type is the sentence-shaped type
- **THEN** no part of speech is written for it, and this is correct rather
  than incomplete

#### Scenario: A multiword expression note
- **WHEN** a note's type is the expression type
- **THEN** no part of speech is written for it

### Requirement: Lemma is derived consistently with the authoring UI
The system SHALL derive a lemma for lexical-item notes by removing any
leading indefinite article or infinitive marker from the headword, using the
same rule the authoring interface uses for the same purpose.

#### Scenario: A verb headword
- **WHEN** a word note's text is an infinitive carrying its marker
- **THEN** its lemma is the text with that marker removed

#### Scenario: A noun headword with an article
- **WHEN** a word note's text carries a leading indefinite article
- **THEN** its lemma is the text with that article removed

#### Scenario: The same note derived by either side
- **WHEN** the authoring interface derives a lemma for a note the import
  already derived one for
- **THEN** both produce the same value

#### Scenario: A note that is not a single lexical item
- **WHEN** a note is an expression rather than a single lexical item
- **THEN** no lemma is derived for it
