# notes-browser

## Purpose

TBD — defines the operator-facing, full-status notes list (draft and ready
alike), distinct from `notes-read-api`'s public ready-only endpoint, with
each row linking directly into the note editor.

## Requirements

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

### Requirement: The notes browser can be filtered by origin
The system SHALL provide an origin filter in the notes browser alongside its
existing status and type filters, offering every permitted origin value plus
an unfiltered default, so the operator can separate hand-authored work from
imported and captured notes.

#### Scenario: Finding one's own authored notes among imported ones
- **WHEN** the operator filters the notes browser to `origin=manual` while
  the database also contains thousands of imported notes
- **THEN** only hand-authored notes are listed

#### Scenario: Reviewing an import
- **WHEN** the operator filters to `origin=import` and `status=draft`
- **THEN** only imported notes still awaiting review are listed

#### Scenario: Default view
- **WHEN** the notes browser is opened with no origin filter chosen
- **THEN** notes of every origin are listed

### Requirement: A note's origin is shown but never offered for editing
The system SHALL display a note's origin in the editor as read-only
information, and SHALL NOT present it as an editable form control, since
origin cannot be changed after creation.

#### Scenario: Viewing an imported note
- **WHEN** the operator opens a note with `origin=import` in the editor
- **THEN** its origin is shown, identifying the source it was imported
  from, with no control that would suggest it can be changed

#### Scenario: Viewing a hand-authored note
- **WHEN** the operator opens a note with `origin=manual` in the editor
- **THEN** its origin is shown as manual, with no editable control
