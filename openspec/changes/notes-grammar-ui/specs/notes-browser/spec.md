## ADDED Requirements

### Requirement: Notes of every status are browsable, filterable, sortable, and searchable
The system SHALL provide a list of all notes regardless of status, filterable
by status and type, sortable, and searchable by text content, distinct from
`notes-read-api`'s public, ready-only endpoint.

#### Scenario: Browsing draft notes
- **WHEN** the operator filters the notes browser to `status=draft`
- **THEN** draft notes are shown, even though they would never appear via
  `GET /api/notes`

#### Scenario: The public read API is unaffected
- **WHEN** the notes browser is used in any way
- **THEN** `GET /api/notes`'s behavior (ready-only, no draft ever returned)
  is unchanged

### Requirement: Each row links directly to the note's editor
The system SHALL make every note in the list directly openable for editing,
with no requirement that the operator know or look up the note's id.

#### Scenario: Opening a note from the list
- **WHEN** the operator clicks a row in the notes list
- **THEN** that note's editor opens, with no id entry required
