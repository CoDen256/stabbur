## ADDED Requirements

### Requirement: A note with stored audio offers a text suggestion transcribed from it
The system SHALL show a "Propose from audio" control on the existing-note
editor whenever the note has `audio_blob` set, opening an accordion with one
row per configured `stt` provider, each showing that provider's transcribed
text and a "Use" button that writes it into the `text` field. This control
SHALL NOT appear on the new-note form or on a note with no stored audio.

#### Scenario: Note has audio
- **WHEN** the operator opens a note that has `audio_blob` set
- **THEN** a "Propose from audio" control is available, and opening it fires
  a transcription request per configured `stt` provider against that note's
  stored audio

#### Scenario: Note has no audio
- **WHEN** the operator opens a note with no `audio_blob`
- **THEN** no "Propose from audio" control is shown

#### Scenario: Using a transcription on an empty text field
- **WHEN** the operator clicks "Use" on a provider's transcription and the
  note's `text` field is currently empty
- **THEN** the transcription is written into `text` immediately, with no
  confirmation prompt

#### Scenario: Using a transcription over existing text
- **WHEN** the operator clicks "Use" on a provider's transcription and the
  note's `text` field already has a non-empty value
- **THEN** the operator is asked to confirm before the existing value is
  overwritten
