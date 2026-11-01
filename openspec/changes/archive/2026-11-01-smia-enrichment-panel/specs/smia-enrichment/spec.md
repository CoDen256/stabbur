## ADDED Requirements

### Requirement: Enrichment lookups are proxied to smia, never called directly from the browser
The system SHALL provide stabbur backend endpoints that forward `ipa`,
`translations`, `inflections`, and `tts` lookups to smia on the operator's
behalf, attaching smia's own auth token server-side, so the browser never
holds or sends a smia credential and smia's network address is never exposed
to the client.

#### Scenario: Operator requests a suggestion
- **WHEN** the browser calls the stabbur enrichment endpoint for a given kind
  (e.g. `ipa`) with a provider and the kind's input fields
- **THEN** stabbur forwards the equivalent request to smia's `POST /<kind>`
  with its own `SMIA_AUTH_TOKEN`, and returns smia's response body to the
  browser unchanged

#### Scenario: Browser never sees smia's token or address
- **WHEN** inspecting any request the note editor makes while suggesting
- **THEN** every request target is a stabbur-origin path, authenticated with
  the operator's existing stabbur bearer token only

### Requirement: The provider catalog is reachable through stabbur
The system SHALL expose smia's provider catalog (which providers are
currently configured per kind) through a stabbur-side endpoint, so the UI can
render per-kind suggestion rows without talking to smia directly.

#### Scenario: Client loads the suggestion panel
- **WHEN** the note editor opens a suggestion panel for a kind
- **THEN** it calls stabbur's provider-catalog endpoint and renders one row
  per provider currently returned for that kind, including providers that are
  dynamically unavailable (shown as such, not omitted silently without reason)

### Requirement: A lookup failure is surfaced as-is, with no retry or fallback
The system SHALL pass through a provider's failure (no entry found, provider
error, or unavailable) to the client exactly as smia reported it, and SHALL
NOT automatically retry the same kind against a different provider.

#### Scenario: Provider has no entry for the requested input
- **WHEN** smia responds that the named provider found nothing for the given
  input (e.g. an inflected surface form with no lexicon entry)
- **THEN** stabbur's proxy returns that failure to the client unchanged, and
  does not call any other provider in response

#### Scenario: Unknown provider or kind requested
- **WHEN** the client names a provider not currently configured for the kind,
  or a kind stabbur does not proxy
- **THEN** stabbur responds with an error listing the currently available
  providers for that kind, mirroring smia's own unknown-provider /
  provider-required error shape

### Requirement: Using a TTS candidate stores real stabbur-owned audio
The system SHALL, when an operator selects a `/tts` candidate to use for a
note, fetch that candidate's audio bytes from smia server-side and store them
through stabbur's own blob storage — never write a note's `audio_blob` as a
reference into smia's cache, per stabbur owning the canonical learning audio.

#### Scenario: Operator uses a TTS candidate
- **WHEN** the operator clicks "Use" on a `/tts` candidate in the audio
  suggestion panel
- **THEN** stabbur fetches the selected candidate's audio bytes from smia,
  uploads them through its existing blob-upload path, and returns the
  resulting stabbur `sha256` so the client can attach it as the note's
  `audio_blob`
