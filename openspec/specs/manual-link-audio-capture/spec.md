# manual-link-audio-capture

## Purpose

Turns an operator-supplied link (a direct audio file URL, or a YouTube URL +
timecode) into a stabbur-owned, content-addressed audio blob — the other
half of smia's `forvo`/`filmot` manual-link `/tts` providers, which have no
API and only ever return a link to their own site for a human to check by
hand.

## Requirements

### Requirement: A directly-linked audio file can be captured as a blob
The system SHALL provide a backend endpoint that, given a URL to a direct
audio file, downloads it server-side and stores the resulting bytes as a
content-addressed blob, returning the resulting hash unchanged (no
transcoding).

#### Scenario: Capturing a Forvo audio link
- **WHEN** the operator submits a direct audio file URL
- **THEN** the system downloads it, stores the bytes as a blob, and returns
  that blob's sha256

#### Scenario: Submitted link is not audio
- **WHEN** the operator submits a URL whose response is not recognizable as
  audio (e.g. an HTML page)
- **THEN** the system rejects the request with a clear error, and does not
  store the response as a blob

### Requirement: A YouTube URL with a timecode can be captured as a short audio clip
The system SHALL provide a backend endpoint that, given a YouTube URL
carrying a timecode, downloads only the audio for a window of two seconds
before and two seconds after that timecode — not the full video — and
stores the resulting clip as a content-addressed blob.

**Known-blocked as of 2026-11-02**: implemented, but still failing against
real YouTube after several rounds of live debugging (stale yt-dlp pin,
missing JS runtime / bot-check, read-only cookies file / format selection,
player-client-sourced 403s each fixed in turn, with a further failure still
unresolved) — see
`openspec/changes/archive/2026-11-02-manual-link-audio-capture/tasks.md`
task 6.3 for the full history before continuing this.

#### Scenario: Capturing a filmot-found YouTube moment
- **WHEN** the operator submits a YouTube URL with a timecode
- **THEN** the system downloads a roughly four-second audio window centered
  on that timecode and stores it as a blob, returning that blob's sha256

#### Scenario: URL has no timecode
- **WHEN** the operator submits a YouTube URL with no timecode
- **THEN** the system rejects the request rather than downloading the full
  video

### Requirement: Both capture endpoints reject unsafe or malformed targets
The system SHALL reject a submitted URL that is not `http`/`https`, or that
resolves to a private, loopback, or link-local address, before attempting
any download.

#### Scenario: Non-HTTP scheme submitted
- **WHEN** the operator submits a `file://` or other non-http(s) URL
- **THEN** the request is rejected before any fetch is attempted

#### Scenario: URL resolves to an internal address
- **WHEN** a submitted URL resolves to a private, loopback, or link-local
  address
- **THEN** the request is rejected before any fetch is attempted
