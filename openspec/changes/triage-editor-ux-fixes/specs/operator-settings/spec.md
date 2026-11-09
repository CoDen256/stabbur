## ADDED Requirements

### Requirement: Triage navigation can autosave edits or require an explicit save
The system SHALL store an operator preference, with two values
(`autosave`, `manual`), governing whether triage's "Send to back", "Skip",
and "Go to previous" actions save the note under review's current edits
before acting. The preference SHALL apply uniformly to all three actions —
there is no way to configure one independently of the others. The default,
read when the preference has never been set, SHALL be `autosave`, matching
"Send to back"'s behavior before this preference existed, so no operator's
experience changes until they explicitly opt into `manual`.

#### Scenario: Reading the default before it has ever been set
- **WHEN** settings are read and the triage-navigation-save preference has
  never been written
- **THEN** it reads as `autosave`

#### Scenario: Switching to manual
- **WHEN** the operator sets the preference to `manual` from the settings
  page
- **THEN** subsequent Send to back, Skip, and Go to previous actions in
  triage no longer save the note under review's edits automatically
