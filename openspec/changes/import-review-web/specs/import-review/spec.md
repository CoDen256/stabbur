## ADDED Requirements

### Requirement: One candidate is presented at a time and replaced on decision
The system SHALL present exactly one candidate at a time, showing its
content, its provenance and its judgement evidence together, and SHALL
replace it with the next candidate as soon as a decision is made, with no
accumulating scrollback.

#### Scenario: Deciding a candidate
- **WHEN** the operator decides the candidate currently on screen
- **THEN** that candidate is replaced by the next one in queue order

#### Scenario: Distinguishing one candidate from the next
- **WHEN** consecutive candidates are reviewed
- **THEN** each is visually self-contained, with no ambiguity about which
  content belongs to the candidate currently being decided

#### Scenario: Progress is visible
- **WHEN** a candidate is on screen
- **THEN** the operator can see how many candidates have been reviewed and
  how many remain

### Requirement: A decision costs exactly one keypress
The system SHALL record a decision on a single keypress, with no
confirmation step and no separate submit action.

#### Scenario: Rejecting a known word
- **WHEN** the operator presses the key meaning "I already know this"
- **THEN** the decision is recorded immediately and the next candidate is
  presented

#### Scenario: Accepting an unknown word
- **WHEN** the operator presses the key meaning "this is new to me"
- **THEN** the decision is recorded immediately and the next candidate is
  presented

### Requirement: The interface asks whether the operator already knows the word
The system SHALL frame the review decision as whether the operator already
knows the word — already known meaning the candidate is not imported, new
meaning it is — rather than presenting the pipeline's own accept/reject
vocabulary as the operator-facing choice.

#### Scenario: Labelling the actions
- **WHEN** the operator is shown the available actions
- **THEN** they are described in terms of whether the word is already known,
  not in terms of accepting or rejecting

#### Scenario: The stored decision is unchanged
- **WHEN** the operator indicates they already know a word
- **THEN** the decision recorded for that candidate is the same `reject`
  value the pipeline already uses, with no change to what downstream stages
  read

### Requirement: Decisions can be undone several steps back
The system SHALL allow the operator to reverse recent decisions in reverse
chronological order, returning each reversed candidate to the queue, and
SHALL allow more than one step to be reversed.

#### Scenario: Correcting a mis-press noticed immediately
- **WHEN** the operator reverses the decision just made
- **THEN** that candidate is returned to the queue and its recorded decision
  is removed

#### Scenario: Correcting a mis-press noticed several candidates later
- **WHEN** the operator reverses decisions repeatedly
- **THEN** each reversal steps one further back through the decisions made,
  in reverse order

#### Scenario: Recent decisions are visible
- **WHEN** the operator is reviewing
- **THEN** the most recent decisions remain visible, so an error made
  several candidates ago can be noticed

### Requirement: Human audio is playable during review
The system SHALL play a candidate's audio on demand during review, and SHALL
offer audio only where a human recording exists.

#### Scenario: A candidate with a human recording
- **WHEN** a candidate whose audio comes from a human-recorded source is
  presented
- **THEN** its audio can be played, and replayed, without leaving the
  candidate

#### Scenario: A candidate whose only audio is synthesised
- **WHEN** a candidate's only available audio is machine-synthesised
- **THEN** the candidate is presented as having no audio, matching what it
  will have once imported

#### Scenario: Audio comes from the source archives
- **WHEN** audio is played
- **THEN** it is read from the original source archives, with no separate
  extraction step required before review can begin

### Requirement: Review is triage only, with no field editing
The system SHALL NOT offer any means of editing a candidate's content during
review, because every accepted candidate is created as an editable draft in
stabbur where authoring properly belongs.

#### Scenario: The available actions
- **WHEN** the operator reviews a candidate
- **THEN** the only decisions available concern whether to import it, with
  no field-editing action offered

### Requirement: Review resumes where it left off
The system SHALL derive the operator's position from the decisions already
recorded, so that review can be stopped and resumed across sessions without
losing progress, and SHALL NOT require a separately stored cursor.

#### Scenario: Resuming a later session
- **WHEN** review is reopened after being closed partway through the queue
- **THEN** it resumes with the first candidate that has no decision recorded

#### Scenario: Re-deriving candidates after a pipeline fix
- **WHEN** earlier pipeline stages are re-run and every candidate is
  regenerated
- **THEN** decisions already recorded are preserved and those candidates are
  not presented again
