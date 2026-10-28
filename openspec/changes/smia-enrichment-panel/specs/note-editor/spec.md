## ADDED Requirements

### Requirement: Transcription, translations, and audio fields offer provider-sourced suggestions
The system SHALL provide a "Suggest" control next to the transcription field,
the translations list, and the audio panel, each opening an accordion
directly beneath/alongside the field it feeds, listing one row per currently
configured provider for that kind, and letting the operator copy a chosen
candidate into the note with one action.

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

### Requirement: Inflection paradigms are looked up read-only, for manual copy
The system SHALL provide a single inflections lookup panel showing each
configured provider's full paradigm as its own read-only table, with each
form individually copyable, and SHALL NOT auto-fill the note's inflection
fields from a lookup — the operator decides which provider's form to use per
field.

#### Scenario: Looking up inflections
- **WHEN** the operator clicks "Look up paradigm"
- **THEN** one panel opens showing every configured inflections provider's
  paradigm as a separate table, matching the note's current part-of-speech
  shape where the provider's data supports it

#### Scenario: Copying a form
- **WHEN** the operator clicks a form shown in a provider's paradigm table
- **THEN** that form is copied for pasting into the corresponding inflection
  field; the note's inflection fields are not modified automatically

#### Scenario: Providers disagree
- **WHEN** two providers report different forms for the same paradigm slot
- **THEN** the panel surfaces the disagreement rather than silently picking
  one provider's answer

### Requirement: Suggestion panels work on both new and existing notes
The system SHALL make every suggestion panel available on the new-note form
and the existing-note editor alike, driven only by the form's current
in-progress values — never requiring the note to already be saved.

#### Scenario: Suggesting on an unsaved note
- **WHEN** the operator is filling in the new-note form and has not yet saved
- **THEN** every suggestion panel is available and uses the form's current
  field values as its default query, exactly as it would on an existing note
