## MODIFIED Requirements

### Requirement: Individual fields can be taken from a related note
The system SHALL let the operator copy any single field from a related note
into the note being edited, without copying the rest of that note. The
related-notes panel SHALL show each field's actual content next to its
"Take" action — not merely whether the field is present — so the operator
can see what a take would bring in before taking it. Audio SHALL be
previewable (playable) directly in the panel, the same way an audio
suggestion's own candidate can be previewed, without that preview
requiring the field to already be taken.

#### Scenario: Taking audio from a related note
- **WHEN** the operator takes the audio from a related note
- **THEN** the edited note references the same audio, and no second copy of
  the recording is stored

#### Scenario: Taking one field and leaving the others
- **WHEN** the operator takes only the transcription from a related note
- **THEN** every other field of the edited note is unchanged

#### Scenario: Previewing a related note's content before taking it
- **WHEN** a related note has translations, context text, inflections, a
  transcription, or audio
- **THEN** that field's actual value is shown next to its "Take" action,
  not only a presence indicator

#### Scenario: Previewing a related note's audio before taking it
- **WHEN** a related note has audio attached
- **THEN** the operator can play that audio directly in the related-notes
  panel before deciding whether to take it
