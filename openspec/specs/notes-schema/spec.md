# notes-schema

## Purpose

TBD — defines the data model for notes: permanent ids with tombstoning,
language-agnostic fields, flexible translations, the draft/ready status
model, and the structures for inflections and shared grammar rules.

## Requirements

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

### Requirement: Every note asserts its origin positively
The system SHALL store an `origin` on every note, restricted to exactly
`manual`, `capture`, and `import`, and SHALL NOT permit a note to exist
without one. The system SHALL NOT express any origin as the absence of other
data.

#### Scenario: A hand-authored note
- **WHEN** a note is created by the operator in the authoring UI with no
  capture and no import reference
- **THEN** its `origin` is `manual`, stored as that value explicitly rather
  than inferred from null provenance columns

#### Scenario: Attempting an unsupported origin value
- **WHEN** a request attempts to set `origin` to any value other than
  `manual`, `capture`, or `import`
- **THEN** the request is rejected

#### Scenario: The three origins partition every note
- **WHEN** the complete set of notes is grouped by `origin`
- **THEN** every note falls into exactly one of `manual`, `capture`, or
  `import`, with no note uncategorised

### Requirement: An origin claim is backed by its provenance evidence
The system SHALL require `capture_id` to be present when `origin=capture`,
SHALL require `import_ref` to be present when `origin=import`, and SHALL
require both to be absent when `origin=manual`, enforced at the storage
layer rather than by convention.

#### Scenario: Claiming an imported origin without a reference
- **WHEN** a note is written with `origin=import` and no `import_ref`
- **THEN** the write is rejected

#### Scenario: Claiming a captured origin without a capture
- **WHEN** a note is written with `origin=capture` and no `capture_id`
- **THEN** the write is rejected

#### Scenario: Claiming a manual origin while carrying provenance
- **WHEN** a note is written with `origin=manual` and either a `capture_id`
  or an `import_ref`
- **THEN** the write is rejected

### Requirement: Imported notes record which external source they came from
The system SHALL store `import_ref` as a structured value identifying the
external source a note was imported from, including which source, which
note within that source, and which import run produced it.

#### Scenario: An imported note's provenance is auditable
- **WHEN** a note with `origin=import` is read via the authoring API
- **THEN** its `import_ref` identifies the source, the source's own note
  identifier, and the import run

#### Scenario: The reference does not create a dependency
- **WHEN** whatever external store the `import_ref` points at is
  unavailable, moved, or deleted
- **THEN** the note remains fully readable and valid, and `import_ref`
  remains a meaningful record on its own

### Requirement: A note's origin is immutable once created
The system SHALL reject any attempt to change a note's `origin` or
`import_ref` after creation, while continuing to allow every content field
to be edited freely.

#### Scenario: Attempting to rewrite provenance
- **WHEN** a request attempts to change an existing note's `origin` from
  `import` to `manual`
- **THEN** the request is rejected and the stored `origin` is unchanged

#### Scenario: Heavily editing an imported note
- **WHEN** the operator rewrites the text, translations, and inflections of
  a note with `origin=import`
- **THEN** every edit is applied and the note's `origin` remains `import`

#### Scenario: Round-tripping an unchanged origin
- **WHEN** a request includes the note's existing `origin` value unchanged
  alongside content edits
- **THEN** the request is accepted
</content>
</invoke>
