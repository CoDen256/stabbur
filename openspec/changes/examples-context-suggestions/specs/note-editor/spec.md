## ADDED Requirements

### Requirement: The context field offers provider-sourced example sentences
The system SHALL provide a combined suggest control for the note's context
field — the same toggle, live editable shared query, and per-provider rows
used by the other suggestion kinds — querying with the note's `text` and
opening a panel listing one row per configured examples provider, each with
its candidate sentences and an action writing a chosen sentence into the
context field.

Candidates SHALL be presented as Norwegian sentences only. The system SHALL
NOT pair an example with a translation or present one as a translation
candidate, since example lookup answers how a word is used in Norwegian and
translation is a separate kind.

#### Scenario: Suggesting a context sentence
- **WHEN** the operator opens the context field's suggest control
- **THEN** a panel opens showing one row per configured examples provider,
  each listing that provider's candidate sentences with an action that
  writes a chosen one into the context field

#### Scenario: The query comes from the note's text
- **WHEN** the operator opens the context field's suggest control on a note
  with `text = "legge til"`
- **THEN** the query shown and used is `"legge til"`

#### Scenario: A provider with no examples
- **WHEN** a configured provider has no example for the queried word
- **THEN** that provider's row reports an empty result rather than an
  error, and the other providers' rows are unaffected

#### Scenario: Examples are not translated
- **WHEN** any example candidate is shown
- **THEN** no translation of it is displayed or requested

### Requirement: An example candidate shows the provenance its provider reports
The system SHALL display, for each example candidate, the sense it
illustrates and the sub-source it came from, where the provider reports
them, so the operator can distinguish a lexicographer's example filed under
a definition from a naturally-occurring sentence found in a corpus.

Both are optional, and a provider omits either where it has nothing
meaningful to report. The system SHALL show each only when present, and
SHALL NOT substitute a placeholder for an absent one — an example with no
sense is a complete answer, not missing data.

#### Scenario: A dictionary provider's candidate
- **WHEN** a provider returns an example filed under a particular
  definition and reports that sense
- **THEN** the candidate is shown with the sense it illustrates

#### Scenario: A corpus provider's candidate
- **WHEN** a provider returns a sentence drawn from one of its datasets and
  reports which
- **THEN** the candidate is shown with that sub-source named

#### Scenario: A provider reports neither
- **WHEN** a provider returns a candidate with no sense and no sub-source
- **THEN** only the sentence is shown, with no placeholder or empty label
  in place of the missing fields

### Requirement: The number of example candidates requested is an operator control
The system SHALL request a defined number of example candidates per
provider, defaulting to the enrichment service's own default, and SHALL let
the operator ask for more when the default set is unusable.

Because the requested count forms part of the lookup's cache identity,
asking for a different count SHALL be treated as a new lookup rather than
an expansion of the previous one.

#### Scenario: Default request
- **WHEN** the operator opens the context suggest control without changing
  the count
- **THEN** each provider is queried for the service's default number of
  candidates

#### Scenario: Asking for more
- **WHEN** the operator raises the requested count and re-runs
- **THEN** each provider is queried again for that many candidates, as a
  fresh lookup
