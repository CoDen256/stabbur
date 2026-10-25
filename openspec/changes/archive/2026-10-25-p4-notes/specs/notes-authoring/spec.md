## ADDED Requirements

### Requirement: Notes can be created, read, updated, and conditionally deleted
The system SHALL provide create, read, and update operations on notes, and
SHALL restrict hard deletion to notes that have never reached `status=ready`.

#### Scenario: Creating a note
- **WHEN** a new note is submitted with required fields (`type`,
  `source_lang`, `text`)
- **THEN** it is created with `status=draft` unless explicitly set otherwise

#### Scenario: Editing a note after it reached ready
- **WHEN** a note with `status=ready` is edited
- **THEN** the edit succeeds and the note's `status` remains unaffected
  unless explicitly changed

#### Scenario: Attempting to hard-delete a ready note
- **WHEN** a deletion is requested for a note with `status=ready`
- **THEN** the system does not remove the row outright (see `notes-schema`'s
  tombstone requirement)

### Requirement: Authoring is a minimal surface, not a triage workflow
The system SHALL expose authoring as direct create/read/update operations on
individual notes, and SHALL NOT include a capture inbox, enrichment
suggestions, or bulk review — those belong to later, separate work.

#### Scenario: No capture-derived suggestions appear during authoring
- **WHEN** a note is created through the authoring surface
- **THEN** no capture record, enrichment suggestion, or dedup check is
  consulted or required
