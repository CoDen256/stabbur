## ADDED Requirements

### Requirement: stabbur's Postgres matches mjolnir's Postgres major version exactly
The system SHALL run the identical Postgres image tag for `stabbur-postgres`
as `mjolnir-postgres` uses, so that any tool built to connect to one with a
specific client version works identically against the other.

#### Scenario: Comparing both services' Postgres images
- **WHEN** `stabbur-postgres`'s and `mjolnir-postgres`'s image tags are
  compared
- **THEN** they are identical

### Requirement: The version migration preserves all existing data
The system SHALL migrate `stabbur-postgres`'s existing data to the new
version with no data loss, verified by row-count comparison before and
after.

#### Scenario: Migrating live data
- **WHEN** the operator performs the documented migration procedure
- **THEN** every table's row count in the new version matches its row
  count in the old version before migration began

### Requirement: The previous version's data is not deleted as part of this migration
The system SHALL leave the previous Postgres version's data volume intact
and unmodified after migration, available as a fallback.

#### Scenario: Immediately after migration
- **WHEN** the migration procedure completes and the application is
  verified working against the new version
- **THEN** the previous version's data volume still exists, untouched
