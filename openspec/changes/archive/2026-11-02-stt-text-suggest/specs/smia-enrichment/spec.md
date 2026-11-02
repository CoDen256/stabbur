## ADDED Requirements

### Requirement: An audio transcription can be proxied to smia's speech-to-text
The system SHALL provide a stabbur backend endpoint that, given a provider
and a reference to audio already stored in stabbur's own blob storage,
forwards that audio to smia's `POST /stt` as multipart with the operator's
requested provider, and returns the transcription unchanged. Unlike the
JSON-body kinds, this endpoint reads its input from stabbur's own storage
rather than from operator-typed fields, and SHALL require an explicit
`provider` on every request (no single-provider default), matching smia's
own `stt-api` contract.

#### Scenario: Transcribing a note's stored audio
- **WHEN** the browser calls the stabbur stt-enrichment endpoint with a
  provider and the sha256 of audio already in stabbur's blob storage
- **THEN** stabbur reads those bytes locally, forwards them to smia's
  `POST /stt` with the requested provider, and returns `{provider, text}`
  to the browser unchanged

#### Scenario: Provider omitted
- **WHEN** the stt-enrichment endpoint is called without a `provider`
- **THEN** the request is rejected, with no provider silently defaulted

#### Scenario: Referenced audio does not exist in stabbur's blob storage
- **WHEN** the stt-enrichment endpoint is called with a sha256 that has no
  corresponding stored blob
- **THEN** the request fails with a client error, and no call is made to smia
