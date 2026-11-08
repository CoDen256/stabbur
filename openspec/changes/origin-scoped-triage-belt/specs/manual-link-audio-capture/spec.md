## ADDED Requirements

### Requirement: Audio can be captured from any pasted link, independent of a provider
The system SHALL accept an audio link pasted by the operator without
requiring them to first choose a provider row, and SHALL determine from the
link itself how to obtain the audio — fetching a direct audio file, or
extracting a short clip from a video URL carrying a timecode.

The system SHALL apply the same safety check to such a link as to one
pasted into a provider row, rejecting unsupported schemes and hosts
resolving to private, loopback, link-local, reserved, or multicast
addresses before any request is made.

The existing per-provider paste-back inputs SHALL continue to work
unchanged; this adds a provider-independent entry point rather than
replacing them.

#### Scenario: Pasting a direct audio link
- **WHEN** the operator pastes a URL pointing at an audio file and submits
  it
- **THEN** the audio is fetched, stored as a stabbur blob, and attached to
  the note, with the trim control available exactly as for any other
  attached audio

#### Scenario: Pasting a video link with a timecode
- **WHEN** the operator pastes a video URL carrying a timecode and submits
  it
- **THEN** the system attempts to extract a short clip at that timecode
  rather than treating the URL as a direct audio file

#### Scenario: Pasting a link that is neither
- **WHEN** the operator pastes a URL that is neither a direct audio file
  nor a recognised video URL with a timecode
- **THEN** the system reports what it could not do with the link, rather
  than failing silently or storing a non-audio response

#### Scenario: An unsafe link is refused before any request
- **WHEN** the operator pastes a URL whose scheme is unsupported, or whose
  host resolves to a private or loopback address
- **THEN** it is rejected without any network request being made

#### Scenario: Provider rows still accept paste-back
- **WHEN** the operator pastes a link into a specific provider's
  paste-back input
- **THEN** it is captured exactly as before

### Requirement: A capture path known not to work is presented as such
The system SHALL indicate, where a capture path is known to be failing
against its real-world target, that it is known-blocked rather than
presenting it as an available option on equal footing with working paths.

The video-timecode path is in this state: it is implemented but has not
been made to work against real YouTube, while direct audio capture is
confirmed working. Offering a provider-independent paste box makes this
path more prominent than it was inside a single provider's row, so the
distinction has to be visible rather than discovered by the operator.

#### Scenario: Offering the paste control
- **WHEN** the operator is shown the link-capture control
- **THEN** the link kinds it handles are indicated, with any known-blocked
  path marked as such

#### Scenario: A known-blocked path is attempted anyway
- **WHEN** the operator pastes a link of a known-blocked kind
- **THEN** the attempt is still made and its real failure reported, rather
  than being refused pre-emptively
