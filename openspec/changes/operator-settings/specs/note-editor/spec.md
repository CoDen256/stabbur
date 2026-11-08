## MODIFIED Requirements

### Requirement: Translation suggestions are grouped by target language
The system SHALL group translation suggestions by target language, showing
the operator's configured default target languages, and SHALL let the
operator add further target languages to the same panel.

When the operator uses a candidate for a language that already has a
translation on the note, the system SHALL follow the operator's configured
merge mode: either extending the existing translation for that language
with the new candidate, separated by a slash, or adding a separate
translation row for that language.

Changing the merge mode SHALL affect only subsequent actions. It SHALL NOT
rewrite translations already stored on any note.

#### Scenario: Opening the translations suggestion panel
- **WHEN** the operator clicks "Suggest translations"
- **THEN** the panel shows one group per configured default target
  language, each listing every configured translation provider's result for
  that language

#### Scenario: Adding a target language
- **WHEN** the operator enters a language code and adds it to the panel
- **THEN** a new group appears for that language with the same providers
  queried against it, without affecting the existing language groups

#### Scenario: Using the first translation for a language
- **WHEN** the operator uses a candidate for a language the note has no
  translation for yet
- **THEN** a translation row is added for that language, regardless of
  merge mode

#### Scenario: Using a second translation while appending
- **WHEN** the note already has an English translation, the merge mode is
  to append, and the operator uses a second English candidate
- **THEN** that language's existing translation is extended with the new
  candidate separated by a slash, and no second English row is added

#### Scenario: Using a second translation while keeping rows separate
- **WHEN** the note already has an English translation, the merge mode is
  to keep rows separate, and the operator uses a second English candidate
- **THEN** a second English translation row is added, leaving the first
  unchanged

#### Scenario: Other languages are unaffected
- **WHEN** the operator uses a candidate within one language group
- **THEN** any other language's chosen translation is left untouched

### Requirement: Each provider row's query is independently editable and retriable
The system SHALL default every provider's query within a panel to that
panel's shared query field, but SHALL let the operator reveal and edit a
per-provider override to re-fire just that row — so a provider with no
entry for the shared query can be retried against a different input without
affecting other providers' rows. The per-provider override input SHALL be
hidden by default, revealed only via an explicit per-row action, so the
common case (every provider sharing one query) has no extra visible
controls.

When revealed, the override SHALL be prefilled with the panel's shared
query by default, so that adjusting the shared query for one provider does
not require retyping it. The system SHALL allow this to be configured to
open empty instead.

#### Scenario: Retrying a provider with a different input
- **WHEN** a provider's row shows no result for the shared query, the
  operator reveals that row's override, edits it, and retries
- **THEN** only that provider is re-queried with the edited input; other
  providers' rows and results are unaffected

#### Scenario: Override opens prefilled by default
- **WHEN** the operator reveals a provider row's override with the default
  configuration
- **THEN** it contains the panel's current shared query, ready to be
  adjusted

#### Scenario: Override configured to open empty
- **WHEN** the operator has configured overrides to open empty and reveals
  a provider row's override
- **THEN** it is empty with a placeholder, reading as a different input
  rather than a copy

#### Scenario: Collapsing an override falls back to the shared query
- **WHEN** a provider row's override is revealed, then the operator
  collapses it again without having retried
- **THEN** that row's next retry uses the panel's shared query value, not a
  stale override — regardless of what the override had been prefilled with
