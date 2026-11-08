## REMOVED Requirements

### Requirement: A verb note's lemma can be derived from its text
**Reason**: The action existed to strip a leading `"å "` from `text` into
`lemma`. The infinitive marker is no longer expected in `text`, and `lemma`
is now derived reactively rather than on demand, so a button that must be
remembered and pressed has nothing left to do. Replaced by "A word note's
lemma follows its text until the operator edits it" below.

**Migration**: None required. `lemma` remains a stored, editable field with
the same meaning; only the way it is populated in the editor changes. Notes
whose `lemma` was set by the old button are unaffected.

## MODIFIED Requirements

### Requirement: Transcription, translations, and audio fields offer provider-sourced suggestions
The system SHALL provide a combined suggest control next to the
transcription field, the translations list, and the audio panel — a toggle
that opens an accordion directly beneath/alongside the field it feeds, fused
with a live, editable query field showing the value about to be used. The
accordion lists one row per currently configured provider for that kind, and
lets the operator copy a chosen candidate into the note with one action. For
a TTS provider that has no automatable lookup and instead returns a link to
its own site for a human to check by hand, the audio panel SHALL show that
link and accept a pasted-back result (a direct audio URL, or a YouTube URL
with a timecode) instead of reporting it as a plain lookup failure.

A transcription provider's answer SHALL be read according to the `mode`
discriminator on its response, which has two arms: a whole-phrase answer
carrying a flat candidate list, and a per-word answer carrying one entry
per token. A response that carries no `mode` SHALL be read as a
whole-phrase answer.

#### Scenario: Suggesting a transcription
- **WHEN** the operator opens the transcription field's suggest control
- **THEN** a panel opens beneath it showing one row per configured IPA
  provider, each with its candidate(s) and a "Use" button that writes the
  chosen candidate into the transcription field

#### Scenario: A whole-phrase transcription answer
- **WHEN** a provider answers a transcription lookup with a whole-phrase
  result
- **THEN** its candidates are listed exactly as a single-word result's are,
  each with its variety where the provider reports one

#### Scenario: A per-word transcription answer
- **WHEN** a provider has no whole-phrase entry for a multi-word query and
  answers per word instead
- **THEN** the row shows one group per token, in the order the tokens were
  looked up, each listing that token's own candidates with their own "Use"
  action

#### Scenario: Suggesting audio
- **WHEN** the operator opens the audio panel's suggest control
- **THEN** a panel opens showing one row per configured TTS provider with its
  candidate(s), and using one attaches the resulting stabbur-stored audio to
  the note (per the `smia-enrichment` capability's TTS handling)

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
  debugging; only the Forvo scenario above is currently confirmed working

### Requirement: Each provider row's query is independently editable and retriable
The system SHALL default every provider's query within a panel to that
panel's shared query field, but SHALL let the operator reveal and edit a
per-provider override to re-fire just that row — so a provider with no
entry for the shared query can be retried against a different input without
affecting other providers' rows. The per-provider override input SHALL be
hidden by default, revealed only via an explicit per-row action, so the
common case (every provider sharing one query) has no extra visible
controls.

#### Scenario: Retrying a provider with a different input
- **WHEN** a provider's row shows no result for the shared query, the
  operator reveals that row's override, edits it, and retries
- **THEN** only that provider is re-queried with the edited input; other
  providers' rows and results are unaffected

#### Scenario: Collapsing an override falls back to the shared query
- **WHEN** a provider row's override is revealed, then the operator
  collapses it again without having retried
- **THEN** that row's next retry uses the panel's shared query value, not a
  stale override

## ADDED Requirements

### Requirement: Each suggestion kind draws its query from one named field
The system SHALL source each suggestion kind's default query from exactly
one of the note's fields, with no fallback between fields: inflection
lookups SHALL use `lemma`, and transcription, translation, and audio
lookups SHALL use `text`.

The system SHALL NOT apply any further transformation to the chosen field's
value before sending it — in particular it SHALL NOT strip a leading
Norwegian article or infinitive marker, which is the enrichment service's
concern where it applies at all.

#### Scenario: Inflections use the lemma
- **WHEN** a `type=word` note has `text = "legge til"` and `lemma = "legge"`,
  and the operator opens the inflections suggest control
- **THEN** the query shown and used is `"legge"`

#### Scenario: Transcription, translations, and audio use the text
- **WHEN** that same note's transcription, translations, or audio suggest
  control is opened
- **THEN** the query shown and used is `"legge til"`, not the lemma

#### Scenario: An empty field is not substituted
- **WHEN** a kind's source field is empty
- **THEN** the query is empty, and the system does not silently fall back to
  a different field

### Requirement: A word note's lemma follows its text until the operator edits it
The system SHALL keep a word note's `lemma` synchronised with the first
whitespace-separated token of its `text` as the operator types, without
requiring any explicit action. Once the operator edits `lemma` directly,
the system SHALL stop synchronising it for that note and SHALL preserve the
operator's value. Loading a different note SHALL clear that state, so the
next note begins synchronised again.

#### Scenario: Typing a multi-word text
- **WHEN** the operator types `"legge til"` into `text` on a word note whose
  lemma they have not edited
- **THEN** `lemma` reads `"legge"`

#### Scenario: The operator overrides the lemma
- **WHEN** the operator edits `lemma` by hand and then continues editing
  `text`
- **THEN** `lemma` keeps the operator's value and is no longer changed by
  `text`

#### Scenario: A new note starts synchronised again
- **WHEN** the operator has overridden `lemma` on one note and then loads or
  begins a different note
- **THEN** that note's `lemma` synchronises from its own `text` as normal

### Requirement: The new-note form is cleared between notes
The system SHALL clear the new-note form completely once a note has been
created from it, and whenever the operator returns to it — every field, every
suggest control's query and edited-state, any audio chosen from a suggestion
but not yet saved, and any selected upload file.

#### Scenario: Creating a second note after a first
- **WHEN** the operator saves a new note and then returns to the new-note
  form
- **THEN** every field is empty, with none of the previous note's values
  present

#### Scenario: Pending suggested audio does not carry over
- **WHEN** the operator used a TTS suggestion on the new-note form, saved
  the note, and returned to the form
- **THEN** no audio is pending attachment to the next note

### Requirement: Suggestion panels do not outlive the note they were opened for
The system SHALL collapse every suggestion panel and discard its rendered
contents whenever a different note is loaded into a form, so that no panel
ever displays candidates looked up for a different note.

#### Scenario: Opening a second note after suggesting on a first
- **WHEN** the operator opens suggestion panels on one note and then
  navigates to another
- **THEN** every panel on the newly loaded note is collapsed, and reopening
  one performs a fresh lookup rather than showing the previous note's
  candidates

#### Scenario: Panels start closed on the new-note form
- **WHEN** the operator begins a new note
- **THEN** every suggestion panel is closed and empty

### Requirement: Every provider in a panel can be re-run from a visible control
The system SHALL provide a visible control on each suggest control that
re-queries every provider in that panel with the control's current query,
without the operator having to collapse and reopen the panel. The panel
SHALL remain open across the re-run.

#### Scenario: Re-running after editing the shared query
- **WHEN** the operator edits a suggest control's query and activates its
  re-run control
- **THEN** every provider in that panel is queried again with the edited
  value and the panel stays open throughout

### Requirement: An explicitly re-run lookup bypasses the cached answer
The system SHALL request a fresh provider lookup, bypassing the enrichment
service's cached result, when the operator explicitly re-runs a panel or
retries a single provider row. Opening a panel for the first time SHALL NOT
bypass the cache.

Without this, re-running an unchanged query would return the cached answer
and appear to the operator to have done nothing.

#### Scenario: Re-running an unchanged query
- **WHEN** the operator activates a panel's re-run control without changing
  the query
- **THEN** the providers are consulted again rather than the previous
  answers being redisplayed from cache

#### Scenario: Opening a panel normally
- **WHEN** the operator opens a suggestion panel for the first time on a
  note
- **THEN** a cached answer is acceptable and no cache bypass is requested
