# notes-schema

## MODIFIED Requirements

### Requirement: An origin claim is backed by its provenance evidence
The system SHALL require `capture_id` to be present when `origin=capture`,
SHALL require `import_ref` to be present when `origin=import`, and SHALL
require both to be absent when `origin=manual`, enforced at the storage
layer rather than by convention. The system SHALL additionally enforce that
a present `capture_id` references an existing capture, so a captured origin
is referentially backed and not merely non-null.

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

#### Scenario: Referencing a capture that does not exist
- **WHEN** a note is written with `origin=capture` and a `capture_id` that
  matches no stored capture
- **THEN** the write is rejected by the storage layer

#### Scenario: Removing a capture a note still references
- **WHEN** a capture is deleted while a note still references it
- **THEN** the deletion is rejected, so a live note's provenance cannot be
  destroyed from underneath it
