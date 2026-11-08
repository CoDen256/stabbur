## ADDED Requirements

### Requirement: Every note asserts its origin positively
The system SHALL store an `origin` on every note, restricted to exactly
`manual`, `capture`, and `import`, and SHALL NOT permit a note to exist
without one. The system SHALL NOT express any origin as the absence of other
data.

#### Scenario: A hand-authored note
- **WHEN** a note is created by the operator in the authoring UI with no
  capture and no import reference
- **THEN** its `origin` is `manual`, stored as that value explicitly rather
  than inferred from null provenance columns

#### Scenario: Attempting an unsupported origin value
- **WHEN** a request attempts to set `origin` to any value other than
  `manual`, `capture`, or `import`
- **THEN** the request is rejected

#### Scenario: The three origins partition every note
- **WHEN** the complete set of notes is grouped by `origin`
- **THEN** every note falls into exactly one of `manual`, `capture`, or
  `import`, with no note uncategorised

### Requirement: An origin claim is backed by its provenance evidence
The system SHALL require `capture_id` to be present when `origin=capture`,
SHALL require `import_ref` to be present when `origin=import`, and SHALL
require both to be absent when `origin=manual`, enforced at the storage
layer rather than by convention.

#### Scenario: Claiming an imported origin without a reference
- **WHEN** a note is written with `origin=import` and no `import_ref`
- **THEN** the write is rejected

#### Scenario: Claiming a captured origin without a capture
- **WHEN** a note is written with `origin=capture` and no `capture_id`
- **THEN** the write is rejected

#### Scenario: Claiming a manual origin while carrying provenance
- **WHEN** a note is written with `origin=manual` and either a `capture_id`
  or an `import_ref`
- **THEN** the write is rejected

### Requirement: Imported notes record which external source they came from
The system SHALL store `import_ref` as a structured value identifying the
external source a note was imported from, including which source, which
note within that source, and which import run produced it.

#### Scenario: An imported note's provenance is auditable
- **WHEN** a note with `origin=import` is read via the authoring API
- **THEN** its `import_ref` identifies the source, the source's own note
  identifier, and the import run

#### Scenario: The reference does not create a dependency
- **WHEN** whatever external store the `import_ref` points at is
  unavailable, moved, or deleted
- **THEN** the note remains fully readable and valid, and `import_ref`
  remains a meaningful record on its own

### Requirement: A note's origin is immutable once created
The system SHALL reject any attempt to change a note's `origin` or
`import_ref` after creation, while continuing to allow every content field
to be edited freely.

#### Scenario: Attempting to rewrite provenance
- **WHEN** a request attempts to change an existing note's `origin` from
  `import` to `manual`
- **THEN** the request is rejected and the stored `origin` is unchanged

#### Scenario: Heavily editing an imported note
- **WHEN** the operator rewrites the text, translations, and inflections of
  a note with `origin=import`
- **THEN** every edit is applied and the note's `origin` remains `import`

#### Scenario: Round-tripping an unchanged origin
- **WHEN** a request includes the note's existing `origin` value unchanged
  alongside content edits
- **THEN** the request is accepted
