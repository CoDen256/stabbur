## ADDED Requirements

### Requirement: Only ready notes are returned
The system SHALL exclude any note with `status=draft` from the read API's
results, regardless of other filter parameters.

#### Scenario: A draft note is never returned
- **WHEN** the read API is queried with filters that would otherwise match a
  `status=draft` note
- **THEN** that note is excluded from the response

### Requirement: Filterable by source language and update time
The system SHALL support filtering results by `source_lang` and by a
`since` timestamp, with both parameters optional.

#### Scenario: Filtering by source language
- **WHEN** the read API is queried with `source_lang=no`
- **THEN** only notes with that `source_lang` are returned

### Requirement: The response is one-directional — no acknowledgment mechanism
The system SHALL NOT provide any endpoint, field, or mechanism for a caller
to report back which notes it consumed or what it did with them.

#### Scenario: A consumer has no way to mark notes as processed
- **WHEN** a caller has pulled and processed some notes
- **THEN** there is no API call available to inform stabbur of that fact,
  and stabbur's own state is unaffected by the pull having happened

### Requirement: The response shape matches the documented contract exactly
The system SHALL return each note with exactly the fields specified in this
change's `design.md` (D-N4) — no field renamed, omitted, or added without a
corresponding update to that contract.

#### Scenario: A consumer built against the documented shape
- **WHEN** a consumer parses the read API's response using the field names
  and types from `design.md` D-N4
- **THEN** every field is present with the documented name and type
