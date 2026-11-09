## ADDED Requirements

### Requirement: A candidate whose every word is known is skipped only when it is compositional
The system SHALL skip a candidate all of whose words are already known only
when that candidate is sentence-shaped, and SHALL NOT skip a lexical item or
multiword expression on the grounds that all of its words are known.

#### Scenario: A sentence made entirely of known words
- **WHEN** every word of a sentence-shaped candidate is already known
- **THEN** the candidate is skipped

#### Scenario: An idiom made entirely of known words
- **WHEN** every word of a multiword expression is already known but the
  expression itself is not attested
- **THEN** the candidate is still presented for review, because its meaning
  does not follow from its parts

#### Scenario: A single lexical item that is already known as a word
- **WHEN** a single-word candidate's own form is known
- **THEN** it is handled by the existing attestation rule, not by this one

### Requirement: Initial capitalisation gates the fully-known skip
The system SHALL treat an initial capital as a precondition of the
fully-known skip, and SHALL NOT skip any candidate lacking one on the
grounds that its words are known, regardless of its note type, word count, or
how many of its words are known.

#### Scenario: A lowercase expression whose words are all known
- **WHEN** a lowercase candidate's every word is known
- **THEN** it is presented for review

#### Scenario: A lowercase sentence-length candidate
- **WHEN** a candidate is lowercase and several words long, and all its words
  are known
- **THEN** it is still presented for review

#### Scenario: A capitalised candidate with an unknown word
- **WHEN** a capital-initial sentence contains a word that is not known
- **THEN** it is presented for review

### Requirement: The fully-known skip does not depend on whether audio exists
The system SHALL decide the fully-known skip from word knowledge alone, and
SHALL NOT require the absence of audio as a condition, while allowing that
condition to be enabled for comparison.

#### Scenario: A fully-known sentence that has a recording
- **WHEN** a capital-initial sentence whose words are all known also has
  audio
- **THEN** it is skipped

#### Scenario: Reporting the alternative
- **WHEN** the eligibility report is produced
- **THEN** it shows the queue totals both with and without the audio
  condition applied

### Requirement: Proper nouns, derived nationality words and numerals are skipped
The system SHALL skip lexical-item candidates that are proper nouns, words
derived from proper nouns, or wholly numeric expressions.

#### Scenario: A place or personal name
- **WHEN** a single-token candidate's own text and its translation are both
  capitalised
- **THEN** it is skipped as a proper noun

#### Scenario: A word derived from a proper noun
- **WHEN** a candidate's text is lowercase and its translation is
  capitalised
- **THEN** it is skipped as derived from a proper noun

#### Scenario: A number word
- **WHEN** a candidate's entire text is a number expression
- **THEN** it is skipped as a numeral

#### Scenario: A word that merely contains a number
- **WHEN** a candidate's text contains a number word as part of a longer
  phrase
- **THEN** it is not skipped as a numeral

#### Scenario: A sentence whose translation begins with a capital
- **WHEN** a sentence-shaped candidate's translation begins with a capital
  because it is a sentence
- **THEN** it is not skipped as a proper noun

### Requirement: Sentences mistyped as lexical items are re-typed where types are assigned
The system SHALL detect a candidate whose source placed sentence content in a
single-word field and assign it the sentence-shaped note type, at the stage
where note types are determined rather than in each rule that consumes them.

#### Scenario: A source field holding a sentence
- **WHEN** a source's single-word field contains a full sentence
- **THEN** that candidate is typed as sentence-shaped

#### Scenario: Downstream consumers see the corrected type
- **WHEN** any later stage reads such a candidate's note type
- **THEN** it reads the corrected type, with no rule needing to re-detect it

### Requirement: Candidates are pushed in review order
The system SHALL create notes in the same order the review queue presented
them, so that the ordering the operator reviewed in is the ordering recorded
downstream.

#### Scenario: Pushing accepted candidates
- **WHEN** accepted candidates are pushed
- **THEN** they are created in the review queue's ordering, not in an
  arbitrary or storage-dependent order

#### Scenario: An interrupted push resumed
- **WHEN** a push is interrupted and resumed
- **THEN** the remaining candidates are still created in review order

### Requirement: A recorded decision outranks a later skip rule
The system SHALL keep a candidate that already carries an operator decision
eligible and decided, and SHALL NOT allow a newly-introduced skip rule to
remove it from the operator's record.

#### Scenario: A new rule contradicting an accepted candidate
- **WHEN** a newly-introduced rule would skip a candidate the operator has
  already accepted
- **THEN** the candidate remains accepted and eligible for pushing

#### Scenario: New rules apply to undecided candidates
- **WHEN** a newly-introduced rule matches a candidate with no decision
- **THEN** it is skipped as the rule dictates

#### Scenario: Disagreements are reported
- **WHEN** a new rule's verdict contradicts a recorded decision
- **THEN** the disagreement appears in the eligibility report without
  changing the decision

### Requirement: Changes to review eligibility are reported for verification
The system SHALL produce a report comparing review eligibility before and
after a change to the rules, listing every candidate whose eligibility
changed, grouped by the rule responsible, with the evidence behind each — so
that the operator can confirm the filtering was correct and recover anything
wrongly removed.

#### Scenario: Verifying what a new filter removed
- **WHEN** the operator reads the report after new rules are applied
- **THEN** they can see the eligible totals before and after, and the
  contribution of each rule to the difference

#### Scenario: Inspecting a specific rule's effect
- **WHEN** the operator examines one rule in the report
- **THEN** every candidate that rule newly skipped is listed with enough
  content to judge whether the skip was right

#### Scenario: Recovering a wrongly skipped candidate
- **WHEN** the operator finds a candidate that should not have been skipped
- **THEN** it can be returned to the review queue without re-running earlier
  stages or discarding existing decisions

#### Scenario: The report is readable rather than exhaustive output
- **WHEN** the report is produced
- **THEN** it is grouped and summarised such that an incorrect skip is
  noticeable, rather than being an undifferentiated dump
