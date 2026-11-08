## MODIFIED Requirements

### Requirement: A lookup failure is surfaced as-is, with no retry or fallback
The system SHALL pass through a provider's failure (no entry found, provider
error, or unavailable) to the client exactly as smia reported it, and the
proxy SHALL NOT automatically retry the same kind against a different
provider. A single lookup yields a single provider's answer, and that
answer — including its failure — reaches the operator as itself.

This prohibition applies to the proxy's handling of a lookup. It does NOT
prohibit the operator from consulting several providers in an order they
configured themselves, provided that:

- the sequence is initiated by an explicit operator action, not by the
  proxy reacting to a failure;
- each provider is consulted through an ordinary, individually
  pass-through lookup; and
- the provider whose answer was used is identified to the operator, so no
  value ever appears without the operator being able to see where it came
  from.

The distinction is between the proxy silently substituting one provider's
answer for another's, which remains forbidden, and the operator running
down their own list with every step visible, which is permitted.

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

#### Scenario: An operator-configured order is walked
- **WHEN** the operator triggers an action that consults their configured
  providers for a kind in order until one answers
- **THEN** each provider is consulted by its own ordinary lookup, each
  response is passed through unchanged, and the provider that supplied the
  value used is identified

#### Scenario: The proxy still does not substitute on its own
- **WHEN** a single lookup for one named provider fails
- **THEN** stabbur returns that failure and does not consult the next
  provider in the operator's order on its own initiative
