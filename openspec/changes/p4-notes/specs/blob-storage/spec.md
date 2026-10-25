## ADDED Requirements

### Requirement: Audio is addressed by content hash, not an arbitrary id
The system SHALL compute the sha256 of uploaded audio bytes and use that hash
as the blob's sole identity, both for storage location and for retrieval.

#### Scenario: Uploading audio
- **WHEN** an audio file is uploaded
- **THEN** the system computes its sha256 and returns that hash as the
  blob's identifier

### Requirement: Uploading identical bytes is idempotent
The system SHALL NOT create a duplicate file or error when the same audio
bytes are uploaded more than once, returning the same hash each time.

#### Scenario: Re-uploading the same audio
- **WHEN** audio bytes already stored under a given sha256 are uploaded again
- **THEN** no new file is written and the same hash is returned

### Requirement: Blobs are served immutably
The system SHALL serve a stored blob at a URL keyed by its sha256, and SHALL
treat that content as permanently immutable once stored — a given hash's
bytes never change.

#### Scenario: Fetching a stored blob
- **WHEN** a blob is requested by its sha256
- **THEN** the exact bytes originally uploaded under that hash are returned

### Requirement: stabbur is the canonical owner of its audio
The system SHALL store audio as local files under stabbur's own control,
with no dependency on any other service's availability to serve them.

#### Scenario: Serving audio with every other service down
- **WHEN** a blob is requested while no other ecosystem service is reachable
- **THEN** the blob is still served successfully
