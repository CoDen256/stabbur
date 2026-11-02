## ADDED Requirements

### Requirement: A verb note's lemma can be derived from its text
The system SHALL show a "From text" action next to the Lemma field whenever
the note's part of speech is `verb`, which sets `lemma` to the current
`text` value with any leading Norwegian infinitive marker (`"å "`) removed.
This action SHALL NOT be shown for any other part of speech.

#### Scenario: Deriving a verb's lemma
- **WHEN** the operator has `text = "å spise"` and `pos = verb`, and clicks
  "From text" next to the Lemma field
- **THEN** `lemma` is set to `"spise"`

#### Scenario: Action hidden for non-verb parts of speech
- **WHEN** the note's part of speech is anything other than `verb`
- **THEN** no "From text" action is shown next to the Lemma field

## MODIFIED Requirements

### Requirement: Transcription, translations, and audio fields offer provider-sourced suggestions
The system SHALL provide a combined suggest control next to the
transcription field, the translations list, and the audio panel — a toggle
that opens an accordion directly beneath/alongside the field it feeds, fused
with a live, editable query field showing the value about to be used,
defaulting to the note's `lemma` and falling back to `text` when no lemma is
set. The accordion lists one row per currently configured provider for that
kind, and letting the operator copy a chosen candidate into the note with
one action. For a TTS provider that has no automatable lookup and instead
returns a link to its own site for a human to check by hand, the audio panel
SHALL show that link and accept a pasted-back result (a direct audio URL, or
a YouTube URL with a timecode) instead of reporting it as a plain lookup
failure.

#### Scenario: Suggesting a transcription
- **WHEN** the operator opens the transcription field's suggest control
- **THEN** a panel opens beneath it showing one row per configured IPA
  provider, each with its candidate(s) and a "Use" button that writes the
  chosen candidate into the transcription field

#### Scenario: Suggesting audio
- **WHEN** the operator opens the audio panel's suggest control
- **THEN** a panel opens showing one row per configured TTS provider with its
  candidate(s), and using one attaches the resulting stabbur-stored audio to
  the note (per the `smia-enrichment` capability's TTS handling)

#### Scenario: Query defaults to lemma, falls back to text
- **WHEN** a `type=word` note has both `lemma` and `text` set, and the
  operator opens any suggest control
- **THEN** the query field shows and uses `lemma`, not `text`; for a note
  with no `lemma` set (or a non-`word` type, which never has one), the query
  field shows and uses `text`

#### Scenario: Editing the shared query before or after opening
- **WHEN** the operator edits a suggest control's query field and presses
  Enter
- **THEN** every provider in that panel is queried (or re-queried) with the
  edited value, whether the panel was already open or still closed

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

### Requirement: Each provider row's query is independently editable and retriable
The system SHALL default every provider's query within a panel to that
panel's shared query field (`lemma || text`), but SHALL let the operator
reveal and edit a per-provider override to re-fire just that row — so a
provider with no entry for the shared query can be retried against a
different input without affecting other providers' rows. The per-provider
override input SHALL be hidden by default, revealed only via an explicit
per-row action, so the common case (every provider sharing one query) has no
extra visible controls.

#### Scenario: Retrying a provider with a different input
- **WHEN** a provider's row shows no result for the shared query, the
  operator reveals that row's override, edits it, and retries
- **THEN** only that provider is re-queried with the edited input; other
  providers' rows and results are unaffected

#### Scenario: Override starts empty, not copied from the shared query
- **WHEN** the operator reveals a provider row's override input
- **THEN** that input starts empty (with a placeholder), not prefilled with
  the shared query's current value, so it reads unambiguously as a different
  input rather than a copy

#### Scenario: Collapsing an override falls back to the shared query
- **WHEN** a provider row's override is revealed, then the operator
  collapses it again without having retried
- **THEN** that row's next retry uses the panel's shared query value, not a
  stale override
