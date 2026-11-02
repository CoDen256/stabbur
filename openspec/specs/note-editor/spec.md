# note-editor

## Purpose

TBD — defines the operator-facing note editing surface: in-editor audio
playback/trim/replace, a raw-JSON view of the stored record alongside the
structured form, and PoS-driven inflection field prefill when creating a
word note.

## Requirements

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
  further — **known-blocked as of 2026-11-02**: this path is implemented but
  still failing against real YouTube after several rounds of live
  debugging (see `openspec/changes/archive/2026-11-02-manual-link-audio-capture/tasks.md`
  task 6.3 for the full history); only the Forvo scenario above is currently
  confirmed working

### Requirement: Suggestions fire only on explicit operator action
The system SHALL NOT fire any provider lookup automatically as the operator
types; every lookup SHALL be the direct result of the operator opening a
suggestion panel or pressing a per-provider retry control.

#### Scenario: Typing into the text field
- **WHEN** the operator edits the note's `text` or `lemma` field
- **THEN** no provider lookup is triggered until the operator explicitly
  clicks a "Suggest" control

### Requirement: Each provider row's query is independently editable and retriable
The system SHALL default each provider's query to the note's current
text/lemma, but SHALL let the operator edit that provider's input and re-fire
just that row, so a provider with no entry for the inflected form can be
retried against the lemma (or any other input) without affecting other
providers' rows.

#### Scenario: Retrying a provider with a different input
- **WHEN** a provider's row shows no result for the default query and the
  operator edits that row's input and clicks retry
- **THEN** only that provider is re-queried with the edited input; other
  providers' rows and results are unaffected

### Requirement: Translation suggestions are grouped by target language
The system SHALL group translation suggestions by target language, showing
English and German by default, and SHALL let the operator add further target
languages to the same panel.

#### Scenario: Opening the translations suggestion panel
- **WHEN** the operator clicks "Suggest translations"
- **THEN** the panel shows an English group and a German group, each listing
  every configured translation provider's result for that target language

#### Scenario: Adding a target language
- **WHEN** the operator enters a language code and adds it to the panel
- **THEN** a new group appears for that language with the same providers
  queried against it, without affecting the existing language groups

#### Scenario: Using a translation
- **WHEN** the operator clicks "Use" on a candidate within a language group
- **THEN** a new translation row is added to the note's translations list,
  tagged with that group's language, leaving any other language's chosen
  translation untouched

### Requirement: Noun inflection fields are grouped by article, singular, and plural
The system SHALL render a `substantiv` note's inflection fields as three
grouped rows — `article` alone on its own row, `sg_indef`/`sg_def` together
on a second row, and `pl_indef`/`pl_def` together on a third row — rather
than one field per row. This grouping SHALL apply identically wherever the
noun's inflection fields are shown: the note form itself, and any
suggestion-panel paradigm table for a `substantiv` candidate.

#### Scenario: Viewing a noun's inflection fields on the note form
- **WHEN** the operator is editing or creating a `pos=substantiv` note
- **THEN** `article` appears alone on its own row, `sg_indef`/`sg_def` appear
  together on a second row, and `pl_indef`/`pl_def` appear together on a
  third row

#### Scenario: Viewing a noun paradigm candidate in the suggestion panel
- **WHEN** a provider's inflection paradigm for a `substantiv` candidate is
  shown in the suggestion panel
- **THEN** its paradigm cells are grouped into the same three rows as the
  note form's own noun fields

### Requirement: Inflection paradigms are looked up read-only, for manual copy
The system SHALL provide a single inflections lookup panel showing each
configured provider's full paradigm as its own table, with each form
individually copyable, and SHALL additionally let the operator fill a form
directly into its matching inflection field on the note with one click, when
that field exists for the note's current part of speech. The system SHALL
NOT auto-fill the note's inflection fields from a lookup on its own — every
fill remains an explicit, per-field operator action.

#### Scenario: Looking up inflections
- **WHEN** the operator clicks "Look up paradigm"
- **THEN** one panel opens showing every configured inflections provider's
  paradigm as a separate table, matching the note's current part-of-speech
  shape where the provider's data supports it

#### Scenario: Copying a form
- **WHEN** the operator clicks a form's copy action in a provider's paradigm
  table
- **THEN** that form is copied for pasting anywhere; the note's inflection
  fields are not modified automatically

#### Scenario: Filling a form directly into its field
- **WHEN** the operator clicks a form's "Fill" action in a provider's
  paradigm table, and the note's current part-of-speech has a matching
  inflection field for that paradigm key
- **THEN** that field on the note form is set to the provider's value
  immediately, without affecting any other inflection field

#### Scenario: Fill is unavailable for a non-matching field
- **WHEN** a provider's paradigm includes a key that has no corresponding
  field for the note's current part of speech
- **THEN** only the copy action is offered for that cell, not a fill action

#### Scenario: Providers disagree
- **WHEN** two providers report different forms for the same paradigm slot
- **THEN** the panel surfaces the disagreement rather than silently picking
  one provider's answer, and filling from one provider does not prevent
  filling a different field from a different provider afterward

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
