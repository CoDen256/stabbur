## MODIFIED Requirements

### Requirement: Enrichment lookups are proxied to smia, never called directly from the browser
The system SHALL provide stabbur backend endpoints that forward `ipa`,
`translations`, `inflections`, `tts`, and `examples` lookups to smia on the
operator's behalf, attaching smia's own auth token server-side, so the
browser never holds or sends a smia credential and smia's network address
is never exposed to the client.

The system SHALL proxy exactly those kinds for which a note has a
corresponding field. A kind with no note field SHALL NOT be exposed through
the generic proxy.

#### Scenario: Operator requests a suggestion
- **WHEN** the browser calls the stabbur enrichment endpoint for a given kind
  (e.g. `ipa`) with a provider and the kind's input fields
- **THEN** stabbur forwards the equivalent request to smia's `POST /<kind>`
  with its own `SMIA_AUTH_TOKEN`, and returns smia's response body to the
  browser unchanged

#### Scenario: Operator requests example sentences
- **WHEN** the browser calls the stabbur enrichment endpoint for `examples`
  with a provider and the query text
- **THEN** stabbur forwards it to smia's `POST /examples` and returns the
  response body unchanged, exactly as for any other proxied kind

#### Scenario: Browser never sees smia's token or address
- **WHEN** inspecting any request the note editor makes while suggesting
- **THEN** every request target is a stabbur-origin path, authenticated with
  the operator's existing stabbur bearer token only
