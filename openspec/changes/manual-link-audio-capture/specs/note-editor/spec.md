## MODIFIED Requirements

### Requirement: Transcription, translations, and audio fields offer provider-sourced suggestions
The system SHALL provide a "Suggest" control next to the transcription field,
the translations list, and the audio panel, each opening an accordion
directly beneath/alongside the field it feeds, listing one row per currently
configured provider for that kind, and letting the operator copy a chosen
candidate into the note with one action. For a TTS provider that has no
automatable lookup and instead returns a link to its own site for a human to
check by hand, the audio panel SHALL show that link and accept a pasted-back
result (a direct audio URL, or a YouTube URL with a timecode) instead of
reporting it as a plain lookup failure.

#### Scenario: Suggesting a transcription
- **WHEN** the operator clicks "Suggest pronunciations" next to the
  transcription field
- **THEN** a panel opens beneath it showing one row per configured IPA
  provider, each with its candidate(s) and a "Use" button that writes the
  chosen candidate into the transcription field

#### Scenario: Suggesting audio
- **WHEN** the operator clicks "Suggest" next to the audio panel
- **THEN** a panel opens showing one row per configured TTS provider with its
  candidate(s), and using one attaches the resulting stabbur-stored audio to
  the note (per the `smia-enrichment` capability's TTS handling)

#### Scenario: A manual-link provider's row
- **WHEN** a TTS provider's row (e.g. `forvo` or `filmot`) returns a link to
  its own site rather than a playable candidate
- **THEN** the row shows an "Open ↗" link to that site and an input for the
  operator to paste back what they found there, instead of a "no entry
  found" message

#### Scenario: Pasting back a Forvo link
- **WHEN** the operator pastes a direct audio URL into the `forvo` row and
  submits it
- **THEN** the resulting stabbur-stored audio is attached to the note, and
  the existing trim control is available on it exactly as for any other
  attached audio

#### Scenario: Pasting back a filmot/YouTube link
- **WHEN** the operator pastes a YouTube URL with a timecode into the
  `filmot` row and submits it
- **THEN** the resulting short audio clip is attached to the note, and the
  existing trim control is available on it for the operator to narrow down
  further
