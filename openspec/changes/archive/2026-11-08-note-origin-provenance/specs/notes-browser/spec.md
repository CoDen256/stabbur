## ADDED Requirements

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
