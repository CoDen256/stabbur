## MODIFIED Requirements

### Requirement: Suggestion panels work on both new and existing notes
The system SHALL make every suggestion panel — including the audio (TTS)
panel — available on the new-note form and the existing-note editor alike,
driven only by the form's current in-progress values — never requiring the
note to already be saved. On the new-note form, using a TTS candidate SHALL
attach the resulting audio to the note at creation time, as part of the same
save action, rather than requiring the note to be created first and audio
attached in a separate step.

#### Scenario: Suggesting on an unsaved note
- **WHEN** the operator is filling in the new-note form and has not yet saved
- **THEN** every suggestion panel is available and uses the form's current
  field values as its default query, exactly as it would on an existing note

#### Scenario: Using a TTS candidate while creating a new note
- **WHEN** the operator clicks "Use" on a TTS candidate while filling in the
  new-note form, then saves the note
- **THEN** the created note already has that candidate's audio as its
  `audio_blob`, with no additional attach step required after save

#### Scenario: Choosing both a suggested candidate and a manually uploaded file
- **WHEN** the operator both uses a TTS suggestion and separately picks a
  file in the audio upload control before saving a new note
- **THEN** whichever action happened most recently is what the created note's
  `audio_blob` reflects
