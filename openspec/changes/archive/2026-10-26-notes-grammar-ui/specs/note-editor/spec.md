## ADDED Requirements

### Requirement: Audio can be listened to, trimmed, and replaced from the editor
The system SHALL provide in-editor audio playback, a trim control that sets
`audio_sel_ms`, and a way to replace a note's `audio_blob` with a newly
uploaded file, without requiring the operator to leave the editor or handle
raw millisecond values directly.

#### Scenario: Adjusting a trim range
- **WHEN** the operator drags a trim handle in the editor
- **THEN** `audio_sel_ms` updates to match, and a preview plays back exactly
  the selected range

#### Scenario: Replacing audio
- **WHEN** the operator uploads a new audio file for a note
- **THEN** the new file is stored via the existing blob-upload endpoint and
  the note's `audio_blob` is updated to reference it; the previous blob is
  left untouched in storage (content-addressed, per `blob-storage`)

### Requirement: The note's raw stored record is viewable alongside the structured form
The system SHALL provide a toggle showing the note's full stored
representation as formatted JSON, without requiring a separate tool or
database access.

#### Scenario: Viewing raw JSON
- **WHEN** the operator opens the raw-JSON toggle
- **THEN** the exact fields and values the API would return for that note
  are shown, matching the structured form currently on screen

### Requirement: Creating a word note prefills inflection fields by part of speech
The system SHALL present the correct set of inflection fields for the
selected part of speech immediately upon selection, rather than a blank or
generic field for the operator to shape by hand.

#### Scenario: Selecting "verb" while creating a word note
- **WHEN** the operator selects `pos=verb` on the new-note form
- **THEN** the infinitiv/presens/preteritum/perfektum fields appear, empty
  and ready to fill, with no other PoS's fields shown
