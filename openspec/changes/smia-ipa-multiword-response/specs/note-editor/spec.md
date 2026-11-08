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

A transcription provider's answer SHALL be read according to the `mode`
discriminator on its response, which has two arms: a whole-phrase answer
carrying a flat candidate list, and a per-word answer carrying one entry
per token. A response that carries no `mode` SHALL be read as a
whole-phrase answer, so an older enrichment service remains readable.

#### Scenario: Suggesting a transcription
- **WHEN** the operator opens the transcription field's suggest control
- **THEN** a panel opens beneath it showing one row per configured IPA
  provider, each with its candidate(s) and a "Use" button that writes the
  chosen candidate into the transcription field

#### Scenario: A whole-phrase transcription answer
- **WHEN** a provider answers a transcription lookup with a whole-phrase
  result
- **THEN** its candidates are listed exactly as a single-word result's are,
  each with its variety where the provider reports one, and using one writes
  that transcription into the field

#### Scenario: A per-word transcription answer
- **WHEN** a provider has no whole-phrase entry for a multi-word query and
  answers per word instead
- **THEN** the row shows one group per token, in the order the tokens were
  looked up, each listing that token's own candidates with their own "Use"
  action

#### Scenario: A token the provider has no entry for
- **WHEN** a per-word answer includes a token with no candidates
- **THEN** that token is still shown, in its input position, marked as
  having no entry — it is not omitted from the breakdown and does not cause
  the row to report overall failure

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

#### Scenario: Previewing a TTS candidate before using it
- **WHEN** the operator is shown a TTS candidate in the audio suggest panel
- **THEN** they can play that candidate's audio before deciding whether to
  use it, on both the new-note and existing-note forms, without that
  playback requiring the candidate to already be stored as the note's
  attached audio

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

## ADDED Requirements

### Requirement: An assembled phrase transcription is offered only when the provider supplies one, and is never fabricated
The system SHALL offer an assembled whole-phrase transcription only when
the enrichment service itself supplies one, and SHALL NOT concatenate a
per-word answer's tokens to manufacture one when it does not. When no
assembled string is supplied, the only transcription actions offered SHALL
be per-token ones.

The enrichment service supplies that assembled string **only** when every
token resolved to exactly one candidate; its absence is that service's
explicit signal that assembling the phrase would require a choice it
declines to make on the caller's behalf.

The system SHALL additionally distinguish an assembled string from a
whole-phrase lookup in the way it is presented, rather than showing the two
identically, because an assembled string is a sequence of citation forms
rather than a recorded pronunciation of the phrase.

#### Scenario: Every token resolved to exactly one candidate
- **WHEN** a per-word answer supplies an assembled whole-phrase string
- **THEN** the panel offers it as a single action that fills the
  transcription field, labelled as assembled from the individual words
  rather than as the phrase's recorded pronunciation

#### Scenario: A token resolved ambiguously or not at all
- **WHEN** a per-word answer supplies no assembled string, because some
  token has no candidates or more than one
- **THEN** the panel offers no whole-phrase fill at all, and the operator
  fills the field from individual tokens or by typing it

#### Scenario: The system does not assemble on its own
- **WHEN** a per-word answer supplies no assembled string
- **THEN** the system does not join the tokens' transcriptions to
  manufacture one, even where exactly one candidate happens to be
  selectable per token
