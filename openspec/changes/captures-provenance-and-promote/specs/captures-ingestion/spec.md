## ADDED Requirements
### Requirement: A capture records the source it came from
The system SHALL store a `source` structure on every capture identifying
where the capture was taken, supporting at minimum a web page (`url`, with
optional `title`) and a YouTube cue (`videoId`, cue start and end
timecodes, `url`, optional `title`). The system SHALL NOT require any note
field to carry this information.

#### Scenario: Capturing selected text from a web page
- **WHEN** a capture is ingested with a `source` naming a web page URL
- **THEN** the URL is stored in queryable structure on the capture, and is
  retrievable without parsing any free-text field

#### Scenario: Capturing a YouTube subtitle selection
- **WHEN** a capture is ingested with a `source` naming a video id and a cue
  timecode
- **THEN** the video id and timecode are stored as structured values on the
  capture

#### Scenario: A source shape missing its required locator
- **WHEN** a capture is ingested with a `youtube` source carrying no video
  id, or a `web` source carrying no URL
- **THEN** the request is rejected

#### Scenario: An unrecognised source shape
- **WHEN** a capture is ingested with a `source` containing neither a
  recognised web nor a recognised video shape
- **THEN** the request is rejected rather than stored as an opaque blob

### Requirement: A timecode asserts provenance, not the existence of audio
The system SHALL treat a capture's source timecode as a record of where the
content was found, and SHALL NOT require, imply, or attempt to produce audio
for a capture that carries one.

#### Scenario: A YouTube capture with no audio
- **WHEN** a capture is ingested with a video id and cue timecode and no
  audio reference
- **THEN** it is stored successfully with no audio, and the system makes no
  attempt to fetch or clip media

### Requirement: Ingesting a capture creates its draft note atomically
The system SHALL, on ingesting a capture, create both the capture and a
note referencing it in a single transaction, with the note's origin
asserting that it came from a capture, and SHALL return both.

#### Scenario: A capture arrives
- **WHEN** a capture is ingested
- **THEN** a note is created in the same transaction with `origin=capture`,
  `capture_id` set to that capture, and `status=draft`, and the response
  carries both the capture and the note

#### Scenario: Note creation fails validation
- **WHEN** the note implied by an ingested capture would be invalid
- **THEN** neither the capture nor the note is stored, and the request is
  rejected

#### Scenario: No capture exists without a note
- **WHEN** the complete set of captures is compared against the notes
  referencing them
- **THEN** every capture has at least one note referencing it

### Requirement: Ingestion is idempotent on a client-supplied id
The system SHALL require the capture client to supply the capture's id, and
SHALL treat a repeated ingestion of an already-known id as a success that
returns the existing capture and note rather than creating a second pair.

#### Scenario: A client retries after losing the response
- **WHEN** a capture is ingested twice with the same client-supplied id
- **THEN** exactly one capture and one note exist, and the second request
  succeeds

#### Scenario: Ingestion with no id
- **WHEN** a capture is ingested with no id
- **THEN** the request is rejected rather than assigned a server-generated id

#### Scenario: The same text captured from two places
- **WHEN** identical selected text is ingested twice with different ids and
  different sources
- **THEN** two distinct captures and two distinct notes exist

### Requirement: A capture preserves what was captured, independent of later edits
The system SHALL store the selected text, surrounding context, and the
translations as they were captured, and SHALL NOT update them when the
promoted note's corresponding fields are subsequently edited.

#### Scenario: Editing a promoted note heavily
- **WHEN** the operator rewrites the text and translations of a note with
  `origin=capture`
- **THEN** the note reflects every edit and the capture still reports the
  original selected text and the translations as captured

#### Scenario: Translations are stored as the providers answered them
- **WHEN** a capture is ingested carrying translations tagged with the
  provider and language codes the translation service used
- **THEN** those values are stored unchanged, with no rewriting of provider
  or language codes

### Requirement: A capture's audio is a reference to stored bytes
The system SHALL accept a capture's audio only as a reference to an
already-stored content-addressed blob, together with an optional selection
range within it, and SHALL NOT accept audio bytes on the ingestion endpoint.

#### Scenario: A capture carrying a recording
- **WHEN** a capture is ingested referencing a stored blob and a selection
  range
- **THEN** both the reference and the range are stored on the capture,
  unmodified

#### Scenario: A text capture
- **WHEN** a capture is ingested with no audio reference
- **THEN** it is stored successfully with no audio

### Requirement: Captures whose audio no note has claimed are queryable
The system SHALL provide a query returning captures that carry audio which
the notes referencing them do not yet use, so that a recording can be made
before the note it belongs to is chosen.

#### Scenario: A recording waiting for a note
- **WHEN** a capture carrying audio exists and no note references that same
  audio
- **THEN** that capture appears in the unattached-audio query

#### Scenario: The recording is attached to a note
- **WHEN** a note is updated to carry that capture's audio reference
- **THEN** the capture no longer appears in the unattached-audio query

#### Scenario: A capture with no audio
- **WHEN** a capture carrying no audio exists
- **THEN** it never appears in the unattached-audio query

### Requirement: A capture is readable on its own
The system SHALL expose a capture by id, so a note's provenance can be
displayed without embedding capture data in note listings.

#### Scenario: Reading a note's provenance
- **WHEN** a note with `origin=capture` is displayed and its capture is
  fetched by id
- **THEN** the capture's source, selected text, and context are returned

### Requirement: Capture provenance is never exposed through the public read API
The system SHALL NOT add capture source data to the public notes read API,
whose shape remains unchanged.

#### Scenario: A promoted capture read through the public API
- **WHEN** a note with `origin=capture` is returned by the public read API
- **THEN** the response carries the capture reference only, with no source,
  URL, title, or timecode, and the response shape is identical to that of
  any other note
