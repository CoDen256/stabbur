## ADDED Requirements

### Requirement: External vocabulary sources are ingested verbatim before any transformation
The system SHALL parse each external source into a per-source raw record
preserving every original field value unchanged, and SHALL keep that raw
record available for the rest of the pipeline, so that a parsing or mapping
error can be corrected without re-reading the source archives.

#### Scenario: Ingesting an Anki archive
- **WHEN** an `.apkg` archive is ingested
- **THEN** every note in it is recorded with its original field values, its
  note type, its tags, and its own source identifier

#### Scenario: Re-running a later stage after a mapping bug
- **WHEN** a field-mapping error is discovered after ingest has completed
- **THEN** the mapping can be corrected and re-applied without re-parsing
  the source archives

#### Scenario: Sources with incompatible field models
- **WHEN** sources with different and incompatible field models are ingested
- **THEN** each is parsed by rules specific to that source, with no
  requirement that they share a field structure

### Requirement: Source-specific notation is parsed before a candidate's shape is determined
The system SHALL interpret each source's own notation conventions for
encoding inflection and gender, and SHALL determine whether a candidate is a
single lexeme or a multiword expression only after that notation has been
removed.

#### Scenario: A noun carrying a gender marker
- **WHEN** a wordlist entry reads `område /et`
- **THEN** it is treated as the single-word lexeme `område` with neuter
  gender recorded, not as a two-word expression

#### Scenario: A verb carrying a past-tense suffix
- **WHEN** a wordlist entry reads `spå /-dde`
- **THEN** it is treated as the single-word lexeme `spå` with its past form
  recorded

#### Scenario: A genuine multiword expression
- **WHEN** an entry reads `være i stand til` and contains no notation markers
- **THEN** it is treated as a multiword expression

### Requirement: Candidates are compared as whole lexeme signatures
The system SHALL compare candidates against known material using a lexeme
signature comprising the head lemma, its ordered particles, whether it is
reflexive, and any obligatory complements — such that forms differing in
particles, reflexivity, or complements are distinct.

#### Scenario: A particle verb is distinct from its bare head
- **WHEN** `legge til` is compared against known material containing `legge`
- **THEN** they are treated as different lexemes

#### Scenario: A reflexive form is distinct from its non-reflexive head
- **WHEN** `legge seg` is compared against known material containing `legge`
- **THEN** they are treated as different lexemes

#### Scenario: A specific collocation does not cover the general form
- **WHEN** `legge til` is compared against known material containing
  `legge til noen i kopi`
- **THEN** they are treated as different lexemes

### Requirement: Partial, substring and head-only matching is prohibited
The system SHALL NOT discard a candidate on the basis of a substring match,
a prefix match, a match on its head alone, or a match on any subset of its
tokens. Discarding a candidate SHALL require an exact lexeme signature match.

#### Scenario: A compound word sharing a prefix with a known word
- **WHEN** the candidate `aleneforsørger` is judged against known material
  containing `alene`
- **THEN** the candidate is imported, because a prefix match is not grounds
  for discarding

#### Scenario: A coincidental prefix overlap
- **WHEN** the candidate `allerede` is judged against known material
  containing `alle`
- **THEN** the candidate is imported

#### Scenario: An idiom built entirely from known words
- **WHEN** the candidate `bli kvitt` is judged and every one of its tokens
  appears in known material, but the phrase itself does not
- **THEN** the candidate is imported and flagged, not discarded

### Requirement: The known-set is drawn only from unambiguously Norwegian positions
The system SHALL build the set of already-known lexemes from positions in the
existing learned material that are unambiguously Norwegian, and SHALL NOT
treat text from explanatory prose or answer fields as Norwegian vocabulary.

#### Scenario: A Norwegian-English homograph appearing in English prose
- **WHEN** a Norwegian candidate coincides with an English word that appears
  frequently in the learned material's explanatory prose
- **THEN** the candidate is not discarded on the basis of those prose
  occurrences

#### Scenario: Stabbur's own previously-published content is excluded
- **WHEN** the known-set is extracted from a bundle that also contains cards
  previously generated from stabbur's own notes
- **THEN** those cards are excluded, so the import does not treat its own
  prior output as pre-existing knowledge

### Requirement: Uncertainty always resolves toward importing
The system SHALL import and flag a candidate whenever any step of its
judgement is uncertain, and SHALL NOT discard a candidate on uncertain
evidence.

#### Scenario: Lemma resolution fails for a candidate
- **WHEN** a candidate's lemma cannot be resolved from the available
  inflection data
- **THEN** the candidate is imported and flagged, not discarded

#### Scenario: A candidate's head is known but its full form is not
- **WHEN** a candidate shares a head with known material but differs in
  particles or reflexivity
- **THEN** the candidate is imported, carrying a reference to the known
  related form so the operator can judge it

### Requirement: Every judgement records the evidence that produced it
The system SHALL record, for each candidate, the verdict reached and the
evidence it rests on, including which known material it matched and which
rule applied.

#### Scenario: Reviewing why a candidate was flagged
- **WHEN** the operator examines a flagged candidate
- **THEN** the specific rule that flagged it and the known material it
  relates to are both visible

#### Scenario: Auditing what was discarded
- **WHEN** an import run completes
- **THEN** every discarded candidate is recorded with its evidence and is
  reviewable, so a wrongly discarded lexeme can be found and recovered

### Requirement: One candidate per lexeme, merged by fixed source priority
The system SHALL produce exactly one candidate per lexeme signature,
populating each field from the highest-priority source that supplies a
non-empty value, according to a fixed source priority order.

#### Scenario: A lexeme present in four sources
- **WHEN** a lexeme appears in four sources with differing field coverage
- **THEN** one candidate is produced, each of its fields taken from the
  highest-priority source that supplies that field

#### Scenario: A higher-priority source lacking a field
- **WHEN** the highest-priority source has no value for a field but a
  lower-priority source does
- **THEN** the lower-priority source's value is used

### Requirement: Conflicting values between sources are recorded, not silently dropped
The system SHALL retain the losing value when two sources supply different
non-empty values for the same field, and SHALL flag the candidate as
conflicted.

#### Scenario: Two sources gloss a word differently
- **WHEN** two sources supply different translations for the same lexeme
- **THEN** the candidate is flagged as conflicted and both values are
  visible to the operator

### Requirement: Candidates are reviewed in usefulness order
The system SHALL order the review queue by the usefulness signals available
in the sources — frequency ranking first, then proficiency band, then
position in a textbook progression — so that stopping review at any point
has yielded the most useful candidates.

#### Scenario: Stopping review early
- **WHEN** the operator reviews part of the queue and stops
- **THEN** the candidates reviewed are the highest-ranked ones, and the
  remainder stay queued with their judgements and merges intact

#### Scenario: A candidate with no ranking signal
- **WHEN** a candidate comes only from sources that supply no frequency or
  proficiency signal
- **THEN** it is still queued, ordered after those that have one

### Requirement: The pipeline is stage-wise, resumable, and separately re-runnable
The system SHALL organise the import as discrete stages, each reading the
previous stage's output and writing its own, such that any stage can be
re-run without repeating the others and without discarding the operator's
review decisions.

#### Scenario: Interrupting an import
- **WHEN** an import is interrupted partway through any stage
- **THEN** it can be resumed without repeating already-completed stages

#### Scenario: Correcting the known-set after review has begun
- **WHEN** the known-set extraction is corrected after the operator has
  already reviewed some candidates
- **THEN** judgements can be recomputed while the existing review decisions
  are preserved

#### Scenario: Observing progress
- **WHEN** an import runs
- **THEN** each stage logs what it processed, what it produced, and what it
  discarded, identified by run

### Requirement: Accepted candidates enter stabbur as drafts, never as ready
The system SHALL create each accepted candidate as a note with
`status=draft`, `origin=import`, and an `import_ref` identifying its source,
and SHALL NOT create any note with `status=ready`.

#### Scenario: Pushing an accepted candidate
- **WHEN** the operator accepts a candidate and it is pushed to stabbur
- **THEN** a note is created with `status=draft` and `origin=import`,
  carrying an `import_ref` naming its source, source note, and run

#### Scenario: Review in the import tool does not substitute for stabbur's review
- **WHEN** a candidate has been accepted during import review
- **THEN** the resulting note still requires stabbur's own draft-to-ready
  review before it is considered correct

### Requirement: Pushing is idempotent and traceable back to the created note
The system SHALL record the created note's id on the candidate once pushed,
SHALL skip candidates that already carry one, and SHALL therefore allow an
interrupted push to resume without creating duplicates.

#### Scenario: Resuming an interrupted push
- **WHEN** a push is interrupted after creating some notes and is re-run
- **THEN** only candidates without a recorded note id are pushed

#### Scenario: Undoing an unwanted import
- **WHEN** the operator determines after the fact that a pushed candidate
  should not have been imported
- **THEN** the candidate's recorded note id identifies exactly which note to
  remove

### Requirement: Only human audio is imported
The system SHALL import audio only from sources whose recordings are human,
SHALL NOT import machine-synthesised audio, and SHALL import a candidate
with no audio rather than substituting synthesised audio for it.

#### Scenario: A source containing synthesised audio
- **WHEN** a source's audio is machine-synthesised
- **THEN** none of its audio is imported, while its text content still is

#### Scenario: A candidate with no human audio available
- **WHEN** no accepted source supplies human audio for a candidate
- **THEN** the candidate is imported with no audio, to be voiced later
  during authoring

#### Scenario: The same recording present in two sources
- **WHEN** two accepted sources supply byte-identical recordings for a
  lexeme
- **THEN** one content-addressed blob results, not two

### Requirement: Imported note types are determined per candidate, not per source
The system SHALL determine each candidate's note type from the candidate
itself, and SHALL NOT assume that all candidates from one source share a
type.

#### Scenario: A source mixing single words and full sentences
- **WHEN** a source's primary field contains single lexemes for some notes
  and full sentences for others
- **THEN** each is typed individually, with sentences typed as listening and
  lexemes as word or expression

#### Scenario: Grammar material is not imported
- **WHEN** a source contains grammar exercise material
- **THEN** no note of type grammar and no grammar rule is created from it
