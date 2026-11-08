## ADDED Requirements

### Requirement: Origin may be stated on create, and is derived when omitted
The system SHALL accept an explicit `origin` when a note is created, and
SHALL derive it when omitted — `capture` when a `capture_id` is present,
`manual` otherwise — so that clients written before `origin` existed
continue to work unchanged. The system SHALL NOT derive `origin=import`
under any circumstances.

#### Scenario: An existing client that does not know about origin
- **WHEN** a note is created with no `origin` field and no `capture_id`
- **THEN** the note is created with `origin=manual`

#### Scenario: A note promoted from a capture, origin omitted
- **WHEN** a note is created with a `capture_id` but no `origin`
- **THEN** the note is created with `origin=capture`

#### Scenario: An import reference without an explicit origin
- **WHEN** a note is created with an `import_ref` but no `origin`
- **THEN** the request is rejected, because `import` is never inferred

#### Scenario: Explicitly stating an imported origin
- **WHEN** a note is created with `origin=import` and a valid `import_ref`
- **THEN** the note is created with both stored as given

### Requirement: The authoring list is filterable by origin
The system SHALL allow the operator-only authoring list to be filtered by
`origin`, composable with its existing status, type, part-of-speech,
grammar-rule, and text-search filters.

#### Scenario: Filtering to hand-authored notes
- **WHEN** the authoring list is requested with `origin=manual`
- **THEN** only notes with `origin=manual` are returned

#### Scenario: Combining origin with another filter
- **WHEN** the authoring list is requested with `origin=import` and
  `status=draft`
- **THEN** only notes matching both are returned

#### Scenario: An unsupported origin filter value
- **WHEN** the authoring list is requested with an `origin` value outside
  the permitted set
- **THEN** the request is rejected

#### Scenario: No origin filter given
- **WHEN** the authoring list is requested with no `origin` parameter
- **THEN** notes of every origin are returned

### Requirement: The authoring representation exposes provenance
The system SHALL include `origin` and `import_ref` in the authoring
representation of a note, so the operator-facing UI can display and filter
on them without a second lookup.

#### Scenario: Reading an imported note for authoring
- **WHEN** a note with `origin=import` is fetched via the authoring API
- **THEN** the response includes both its `origin` and its full
  `import_ref`

### Requirement: The public read API's contract is unchanged by provenance
The system SHALL NOT add `origin` or `import_ref` to the public read API's
response, and SHALL NOT offer either as a filter there, because a note's
provenance has no bearing on whether a downstream consumer should use it.

#### Scenario: Reading notes through the public API
- **WHEN** `GET /api/notes` is called after this change
- **THEN** its response shape is identical to before, containing neither
  `origin` nor `import_ref`

#### Scenario: Attempting to filter the public API by origin
- **WHEN** `GET /api/notes` is called with an `origin` parameter
- **THEN** the parameter has no effect on which notes are returned
