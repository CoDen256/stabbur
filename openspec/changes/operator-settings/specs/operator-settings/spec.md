## ADDED Requirements

### Requirement: Operator preferences are stored in stabbur's own database
The system SHALL store operator-level preferences in stabbur's own
database as a single record, served over the authoring API, so that
preferences survive a change of browser or machine and are inspectable
through the same means as any other stabbur record.

The system SHALL NOT keep operator preferences solely in browser-local
storage.

Because stabbur is a single-operator service behind one shared token,
preferences are singular: there is exactly one settings record, not one
per user.

#### Scenario: Preferences survive a different browser
- **WHEN** the operator sets a preference and later opens stabbur from a
  different browser or machine
- **THEN** the preference they set is in effect

#### Scenario: Reading preferences
- **WHEN** a client requests the operator's settings
- **THEN** the stored settings are returned over the authoring API

### Requirement: Unset preferences read as their defaults
The system SHALL return a fully-populated settings object whenever
settings are read, filling in a default for every preference that has not
been explicitly set, so that a caller never has to distinguish
"unconfigured" from "configured".

The system SHALL behave identically whether a preference holds its default
because it was never set or because it was set to that value.

#### Scenario: Reading before anything has been configured
- **WHEN** settings are read and no preference has ever been written
- **THEN** a complete settings object is returned, with every preference at
  its default, and no error or empty response

#### Scenario: Partially configured settings
- **WHEN** the operator has set some preferences but not others
- **THEN** the response carries their values for the ones they set and
  defaults for the rest

### Requirement: Each enrichment kind has an operator-ordered provider preference
The system SHALL store, per enrichment kind, an operator-defined ordering
of that kind's providers together with which of them are enabled. The
first enabled provider in that ordering is that kind's **primary**
provider.

The system SHALL derive the primary from the ordering rather than storing
it separately, so the two cannot disagree.

The system SHALL store only ordering and enablement. It SHALL NOT store
provider definitions, addresses, or credentials, which remain the
enrichment service's own.

#### Scenario: Identifying the primary provider
- **WHEN** a kind's ordering is read and its first provider is enabled
- **THEN** that provider is the kind's primary

#### Scenario: The first provider is disabled
- **WHEN** a kind's ordering is read and its first provider is disabled
- **THEN** the first *enabled* provider is the primary

#### Scenario: Reordering changes the primary
- **WHEN** the operator moves a different provider to the top of a kind's
  ordering and it is enabled
- **THEN** that provider becomes the kind's primary, with no separate
  primary setting to update

### Requirement: Stored provider preferences are reconciled against the live provider catalogue
The system SHALL reconcile a stored provider ordering against the
enrichment service's current catalogue every time the ordering is used,
because the catalogue is owned by that service and can change without
stabbur's involvement.

A stored provider absent from the current catalogue SHALL be skipped rather
than treated as an error, and its stored position and enablement SHALL be
retained so that it resumes its place if it returns.

A provider present in the catalogue but absent from the stored ordering
SHALL be appended to the end of the ordering and treated as enabled, so
that a newly available provider is usable without becoming a primary by
surprise.

#### Scenario: A configured provider is no longer offered
- **WHEN** a provider named in the stored ordering is missing from the
  current catalogue
- **THEN** it is skipped when resolving the order and the primary, without
  an error

#### Scenario: A missing provider returns
- **WHEN** a provider that had disappeared from the catalogue appears again
- **THEN** it resumes its stored position and its stored enabled state,
  rather than being treated as newly discovered

#### Scenario: A new provider appears
- **WHEN** the catalogue offers a provider that the stored ordering does
  not mention
- **THEN** it is appended to the end of that kind's ordering, enabled, and
  does not displace the existing primary

#### Scenario: Every stored provider has vanished
- **WHEN** no provider in a kind's stored ordering is present in the
  current catalogue
- **THEN** the effective ordering is the catalogue's own providers, and the
  kind still resolves a primary

### Requirement: Preferences are editable from a settings page
The system SHALL provide a settings page in the authoring UI's navigation
where every stored preference can be inspected and changed, grouped by what
the preference affects.

The page SHALL present each kind's provider ordering as a reorderable list
showing which provider is currently primary, and SHALL indicate a provider
that cannot answer automatically — such as one that only returns a link to
its own site for a human to check — so the operator can see why it is a
poor choice of primary.

#### Scenario: Changing a provider order
- **WHEN** the operator reorders a kind's providers on the settings page
- **THEN** the new ordering is stored and takes effect on subsequent
  lookups

#### Scenario: Seeing which provider is primary
- **WHEN** the operator views a kind's provider ordering
- **THEN** the provider currently acting as that kind's primary is
  identified

#### Scenario: A manual-link provider is marked as such
- **WHEN** a kind's ordering includes a provider that answers only with a
  link for a human to follow
- **THEN** the page marks it as not automatable
