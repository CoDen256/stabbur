## ADDED Requirements

### Requirement: Related notes are surfaced without being requested
The system SHALL show the notes related to the one the operator is working
on, wherever notes are edited or triaged, without requiring a separate
search action.

#### Scenario: Opening a note for editing
- **WHEN** the operator opens a note
- **THEN** notes related to it are listed alongside it

#### Scenario: Triaging a draft
- **WHEN** the operator reviews a draft in the triage belt
- **THEN** notes related to it are listed alongside it

#### Scenario: A note with nothing related
- **WHEN** no note is related to the one being edited
- **THEN** the absence is shown plainly, rather than an empty control that
  looks broken

#### Scenario: Several related notes
- **WHEN** more than one note is related to the one being edited
- **THEN** all of them are listed, not only the closest match

### Requirement: Each suggestion states why it was surfaced
The system SHALL label every related note with which signal matched it, and
SHALL NOT present a single blended similarity score in place of those
labels.

#### Scenario: A derivationally related word
- **WHEN** a note's text is spelled similarly to another's
- **THEN** that note is listed and labelled as spelled alike

#### Scenario: Two notes sharing an inflected form
- **WHEN** two notes' inflection tables contain the same surface form
- **THEN** they are listed for each other and labelled as the same word
  family

#### Scenario: Two notes sharing a translation
- **WHEN** two notes have a translation in common
- **THEN** they are listed for each other and labelled as related rather
  than duplicate

#### Scenario: A note matched by more than one signal
- **WHEN** a related note matches on both spelling and word family
- **THEN** it appears once, carrying both reasons

### Requirement: Grammatical-article values do not make nouns related
The system SHALL exclude a note's grammatical article from the inflected
forms it compares, so that sharing an article does not make two notes
related.

#### Scenario: Two unrelated nouns of the same gender
- **WHEN** two notes both record the article `en` and share no other
  inflected form
- **THEN** they are not reported as the same word family

### Requirement: Semantically related notes are shown separately and collapsed
The system SHALL present translation-matched notes in a section that is
collapsed by default and distinguished from the signals that indicate a
likely duplicate.

#### Scenario: Synonyms sharing an English gloss
- **WHEN** several notes share a translation but differ in spelling and
  word family
- **THEN** they appear in the collapsed section, presented as related
  information rather than as merge candidates

#### Scenario: Expanding the collapsed section
- **WHEN** the operator expands that section
- **THEN** the translation-matched notes are listed with their reason

### Requirement: Sentence-length notes are excluded from similarity
The system SHALL NOT report similarity for notes whose content is a
sentence rather than a lexical item, because character-level similarity over
sentences is not meaningful.

#### Scenario: A listening note
- **WHEN** a note of type `listening` is edited
- **THEN** no spelling-based similarity is reported for it

### Requirement: Individual fields can be taken from a related note
The system SHALL let the operator copy any single field from a related note
into the note being edited, without copying the rest of that note.

#### Scenario: Taking audio from a related note
- **WHEN** the operator takes the audio from a related note
- **THEN** the edited note references the same audio, and no second copy of
  the recording is stored

#### Scenario: Taking one field and leaving the others
- **WHEN** the operator takes only the transcription from a related note
- **THEN** every other field of the edited note is unchanged

### Requirement: Merging is many-to-one and never automatic
The system SHALL allow one note to absorb several related notes in a single
action, and SHALL NOT merge, resolve, or delete any note without an explicit
operator action.

#### Scenario: Absorbing two notes at once
- **WHEN** the operator merges two related notes into the one being edited
- **THEN** both are absorbed by that one action

#### Scenario: No automatic resolution
- **WHEN** any pair of notes is reported as related, at any similarity
- **THEN** nothing is merged or deleted until the operator acts

### Requirement: Only a draft may be absorbed by a merge
The system SHALL permit a merge only where the absorbed note has status
`draft`, SHALL reject a merge that would absorb a `ready` note, and SHALL
enforce this on the server rather than relying on the interface to prevent
it.

#### Scenario: A ready note absorbing a draft
- **WHEN** a `ready` note absorbs a `draft` note
- **THEN** the merge is permitted

#### Scenario: A draft absorbing a draft
- **WHEN** a `draft` note absorbs another `draft` note
- **THEN** the merge is permitted

#### Scenario: A draft attempting to absorb a ready note
- **WHEN** a merge would absorb a note whose status is `ready`
- **THEN** the merge is rejected and nothing is deleted

#### Scenario: Two ready notes
- **WHEN** a merge between two `ready` notes is attempted
- **THEN** it is rejected and nothing is deleted

#### Scenario: A forbidden merge requested directly
- **WHEN** a forbidden merge is requested without going through the
  interface
- **THEN** it is still rejected

### Requirement: A merge never creates a tombstone
The system SHALL hard-delete the absorbed note, and SHALL NOT set a deletion
marker on it, so that no merge can leave a note resolvable as a tombstone.

#### Scenario: After absorbing a draft
- **WHEN** a draft note has been absorbed by a merge
- **THEN** its row is removed entirely, with no deletion timestamp recorded
  anywhere

#### Scenario: Published progress is unreachable from a merge
- **WHEN** any permitted merge is performed
- **THEN** no note that a downstream consumer could have retrieved is
  removed or marked deleted

### Requirement: Absorbing a draft into a ready note marks it as changed
The system SHALL update the surviving note's modification timestamp when it
absorbs another, so that a consumer filtering on "changed since" sees the
result.

#### Scenario: A ready note absorbs a draft
- **WHEN** a `ready` note absorbs a draft and takes a field from it
- **THEN** its modification timestamp is updated
