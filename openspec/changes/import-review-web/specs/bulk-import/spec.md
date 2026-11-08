## MODIFIED Requirements

### Requirement: Candidates are reviewed in usefulness order
The system SHALL order the review queue by the usefulness signals available
in the sources — frequency ranking first, then proficiency band, then
position in a textbook progression — so that stopping review at any point
has yielded the most useful candidates. The system SHALL use every frequency
ranking a source actually carries, including rankings stored outside a
source's note fields, and SHALL keep rankings from different sources as
distinct signals rather than merging them into a single cross-source rank.

#### Scenario: Stopping review early
- **WHEN** the operator reviews part of the queue and stops
- **THEN** the candidates reviewed are the highest-ranked ones, and the
  remainder stay queued with their judgements and merges intact

#### Scenario: A source whose frequency rank is not a note field
- **WHEN** a source orders its own material by frequency somewhere other
  than in its note fields
- **THEN** that ordering is captured at ingest and used for its candidates

#### Scenario: Two sources with independent frequency rankings
- **WHEN** two sources each supply a frequency ranking over different corpora
- **THEN** they are retained as separate signals, and no combined
  cross-source rank is fabricated from them

#### Scenario: A candidate with no ranking signal
- **WHEN** a candidate comes only from sources that supply no frequency or
  proficiency signal
- **THEN** it is still queued, ordered after those that have one

### Requirement: Only human audio is imported
The system SHALL import audio only from sources whose recordings are human,
SHALL NOT import machine-synthesised audio, and SHALL import a candidate
with no audio rather than substituting synthesised audio for it. The system
SHALL apply this when selecting a candidate's audio, not only when creating
the note, so that a candidate's recorded audio is the audio it will actually
receive.

#### Scenario: A source containing synthesised audio
- **WHEN** a source's audio is machine-synthesised
- **THEN** none of its audio is imported, while its text content still is

#### Scenario: Selecting audio across sources
- **WHEN** a candidate's highest-priority source for audio offers only
  synthesised audio and no human recording exists in any source
- **THEN** the candidate is recorded as having no audio, rather than
  carrying a synthesised reference that is discarded later

#### Scenario: A candidate with no human audio available
- **WHEN** no accepted source supplies human audio for a candidate
- **THEN** the candidate is imported with no audio, to be voiced later
  during authoring

#### Scenario: The same recording present in two sources
- **WHEN** two accepted sources supply byte-identical recordings for a
  lexeme
- **THEN** one content-addressed blob results, not two

## ADDED Requirements

### Requirement: Imported text carries no invisible or non-printing characters
The system SHALL normalise non-breaking and zero-width characters in text
destined for stabbur, at the point the text is normalised rather than at the
point it is displayed, so that no invisible character reaches a note.

#### Scenario: A source using a non-breaking space
- **WHEN** a source's entry separates an article from its word with a
  non-breaking space
- **THEN** the stored text contains an ordinary space

#### Scenario: Normalisation covers the character class, not one character
- **WHEN** a source introduces a non-breaking or zero-width character other
  than the ones currently observed
- **THEN** it is normalised by the same rule, without that rule needing to
  enumerate it individually
