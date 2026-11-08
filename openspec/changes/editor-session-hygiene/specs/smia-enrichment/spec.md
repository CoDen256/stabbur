## ADDED Requirements

### Requirement: An operator-initiated cache bypass is forwarded to the enrichment service
The system SHALL forward a cache-bypass flag to the enrichment service when,
and only when, the client supplies one on an enrichment request, so that a
lookup the operator explicitly asked to re-run consults the provider again
rather than returning the service's cached answer.

The system SHALL NOT originate this flag on its own. Deciding to bypass a
cache is the operator's action, relayed by the proxy; the proxy remains a
pass-through and does not acquire a caching policy of its own.

#### Scenario: Client requests a forced re-run
- **WHEN** the browser sends an enrichment request carrying the cache-bypass
  flag
- **THEN** stabbur forwards it to the enrichment service alongside the
  request's other fields, and returns the resulting response unchanged

#### Scenario: Ordinary lookup is unaffected
- **WHEN** the browser sends an enrichment request without the flag
- **THEN** stabbur forwards the request without it, and a cached answer is
  returned as normal

#### Scenario: The proxy never forces on its own
- **WHEN** stabbur proxies any enrichment request the client did not mark
  for re-run
- **THEN** no cache-bypass flag is added by stabbur
