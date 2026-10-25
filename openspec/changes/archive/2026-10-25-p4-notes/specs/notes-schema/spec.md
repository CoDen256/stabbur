## ADDED Requirements

### Requirement: Notes carry a permanent id, even when removed
The system SHALL assign each note a permanent id at creation that is never
reused, and SHALL preserve that id as a tombstone if the note is ever removed
after having been queryable via the read API, rather than deleting the row
outright.

#### Scenario: Removing a draft note
- **WHEN** a note with `status=draft` that has never been returned by the
  read API is deleted
- **THEN** its row is removed entirely

#### Scenario: Removing a note that may have already been pulled
- **WHEN** a note that has `status=ready` (and is therefore eligible to have
  been returned by the read API) is deleted
- **THEN** its id remains resolvable as a tombstone rather than being freed
  for reuse

### Requirement: Notes are language-agnostic
The system SHALL store `source_lang` as a plain field on every note and
SHALL NOT hardcode any assumption that `source_lang` is always Norwegian,
even though every note today has `source_lang="no"`.

#### Scenario: Querying notes by source language
- **WHEN** the read API is queried with `source_lang=no`
- **THEN** only notes whose `source_lang` field equals `"no"` are returned,
  using the same filtering logic that would apply to any other value

### Requirement: Translations support any number of languages
The system SHALL store `translations` as an array of `{lang, text}` pairs,
with no fixed set of allowed languages and no requirement that any specific
language be present.

#### Scenario: A note with three translations
- **WHEN** a note is created with translations in `en`, `de`, and `fr`
- **THEN** all three are stored and returned, with no language silently
  dropped

### Requirement: Status is draft or ready only, with no published state
The system SHALL restrict `status` to exactly `draft` and `ready`, and SHALL
NOT store any representation of whether a downstream consumer has acted on
the note.

#### Scenario: Attempting to set an unsupported status value
- **WHEN** a request attempts to set `status` to any value other than
  `draft` or `ready`
- **THEN** the request is rejected

### Requirement: Audio is not required for `status=ready`
The system SHALL allow a note to reach `status=ready` with `audio_blob` null,
since "ready" means reviewed and correct, not "has everything a downstream
consumer needs."

#### Scenario: Marking a note ready with no audio yet
- **WHEN** a note with `audio_blob=null` is set to `status=ready`
- **THEN** the update succeeds

### Requirement: Inflections are a flat, Norwegian-shaped structure
The system SHALL store `inflections` as a single flat JSONB object shaped
for Norwegian (per `03-data-model.md`'s per-PoS shapes), without a
per-language wrapper, until a second `source_lang` value actually exists in
the system.

#### Scenario: Storing inflections for a substantiv note
- **WHEN** a `type=word`, `pos=substantiv` note is created with
  `{article, sg_indef, sg_def, pl_indef, pl_def}`
- **THEN** that object is stored exactly as given, with no added
  language-keying wrapper

### Requirement: Grammar notes reference a shared grammar_rule
The system SHALL require `type=grammar` notes to reference a `grammar_rule`
row via `grammar_rule_id`, allowing multiple notes to share the same
explanation.

#### Scenario: Two notes sharing a grammar rule
- **WHEN** two separate `type=grammar` notes are created with the same
  `grammar_rule_id`
- **THEN** both resolve to the same `grammar_rule` content, with no
  duplication of the explanation text
