## ADDED Requirements

### Requirement: Drafted notes can be reviewed one at a time as a queue
The system SHALL provide a triage surface presenting drafted notes one at a
time, advancing to the next without requiring the operator to navigate back
to a listing between notes, and showing how many notes remain in the
current queue.

This surface SHALL be offered alongside the notes browser and the note
editor, not in place of either. The note editor SHALL remain available and
unchanged as the way to open any individual note.

The surface SHALL review **notes**. It SHALL NOT introduce any note status
beyond `draft` and `ready`.

#### Scenario: Reviewing successive notes
- **WHEN** the operator records a verdict on the note in front of them
- **THEN** the next drafted note in the queue is presented immediately,
  with no intervening listing or navigation step

#### Scenario: The editor is unaffected
- **WHEN** the operator opens a single note from the notes browser
- **THEN** the existing note editor opens with all of its capabilities, no
  queue position, and no verdict controls

#### Scenario: An empty queue
- **WHEN** no drafted notes remain for the selected queue
- **THEN** the surface reports that the queue is clear rather than
  presenting an empty form

### Requirement: The triage queue covers exactly one origin at a time
The system SHALL scope the triage queue to a single note origin chosen by
the operator, so that imported, captured, and hand-authored notes are
reviewed as separate queues, each with its own remaining count.

The system SHALL NOT offer a queue spanning more than one origin.
Imported notes arrive in bulk with empty fields and are reviewed quickly,
while hand-authored notes are already considered; interleaving them forces
the operator to switch between two different kinds of attention
unpredictably.

#### Scenario: Triaging an import
- **WHEN** the operator selects the imported-notes queue
- **THEN** only drafted notes with that origin are presented, and the
  remaining count reflects only those

#### Scenario: Switching queues
- **WHEN** the operator switches to the hand-authored queue
- **THEN** only drafted hand-authored notes are presented, and the
  imported queue's remaining count is unaffected by that switch

#### Scenario: Origin remains read-only
- **WHEN** a note is presented for triage
- **THEN** its origin is shown but offered no editing control, consistent
  with origin being unchangeable after creation

### Requirement: Each note is resolved by one of four verdicts
The system SHALL offer, in a fixed position that does not move as the
note's content changes, exactly four actions on the note under review:

- **Accept** — set the note's status to `ready`, saving any edits, and
  advance.
- **Send to back** — save any edits and return the note to the queue so it
  is presented again only after every other note currently awaiting
  review.
- **Delete** — delete the note, following the system's existing deletion
  rules, and advance.
- **Skip** — advance without saving, changing status, or recording
  anything.

Accepting SHALL be the only action that sets a note to `ready`. Prefilling
or editing a field SHALL NOT advance a note's status on its own.

#### Scenario: Accepting a note
- **WHEN** the operator accepts the note under review
- **THEN** its edits are saved, its status becomes `ready`, and the next
  note is presented

#### Scenario: Sending a note to the back
- **WHEN** the operator sends the note under review to the back
- **THEN** its edits are saved, it is not marked ready, and it is
  presented again only after the rest of the queue

#### Scenario: A deferred note's edits survive
- **WHEN** the operator edits several fields and then sends the note to the
  back
- **THEN** those edits are present when the note comes round again

#### Scenario: Skipping a note
- **WHEN** the operator skips the note under review
- **THEN** nothing is saved, its status is unchanged, and the next note is
  presented

#### Scenario: Deleting a note
- **WHEN** the operator deletes the note under review
- **THEN** it is deleted under the existing deletion rules and the next
  note is presented

#### Scenario: Verdict controls do not move
- **WHEN** notes of differing length and field count are presented in
  succession
- **THEN** the verdict controls remain in the same position throughout

### Requirement: Empty fields are prefilled from the operator's primary providers
The system SHALL fill a note's empty fields from the operator's configured
primary provider for each kind, consulting the next provider in their
configured order when one has no entry, and stopping at the first that
answers.

The system SHALL NOT replace any field that already has a value, whether
the operator typed it or the note arrived carrying it. Prefill fills gaps
only.

Each lookup SHALL remain an ordinary, individually passed-through
enrichment request initiated by the operator's own action, consistent with
the enrichment capability's rule that the proxy itself never substitutes
one provider's answer for another's.

#### Scenario: Filling an empty field
- **WHEN** a note under review has no transcription and the operator's
  primary transcription provider has an entry
- **THEN** that provider's answer is placed in the transcription field

#### Scenario: Falling through to the next provider
- **WHEN** the primary provider for a kind has no entry
- **THEN** the next enabled provider in the operator's order is consulted,
  and so on until one answers or the order is exhausted

#### Scenario: No provider answers
- **WHEN** no provider in the order has an entry for a kind
- **THEN** that field is left empty and the remaining fields are still
  filled

#### Scenario: An existing value is never overwritten
- **WHEN** a note arrives with a translation already set
- **THEN** prefill leaves it untouched, even if a provider would have
  answered for that kind

#### Scenario: An edited value is never overwritten
- **WHEN** the operator types into a field and prefill subsequently runs
- **THEN** the operator's value is preserved

### Requirement: Prefill runs automatically or on demand, as the operator configures
The system SHALL let the operator choose whether prefill runs as soon as a
note is presented for review, or only when they activate a fill control,
and SHALL provide that fill control in either mode so a note can be
refilled after its query has been changed.

#### Scenario: Automatic prefill
- **WHEN** the operator has chosen automatic prefill and a note is
  presented
- **THEN** its empty fields are filled without further action

#### Scenario: On-demand prefill
- **WHEN** the operator has chosen on-demand prefill and a note is
  presented
- **THEN** no provider is consulted until the operator activates the fill
  control

#### Scenario: Refilling after changing a query
- **WHEN** the operator edits a note's text and activates the fill control
- **THEN** the empty fields are filled again using the new value

### Requirement: A prefilled field shows which provider supplied its value
The system SHALL display, for each field filled by prefill, which provider
the value came from, so that no value appears in a reviewed note without
the operator being able to see its source.

This is required rather than cosmetic: consulting providers in a
configured order is permitted only where the answering provider is
identified.

#### Scenario: Reviewing a prefilled note
- **WHEN** a note's fields have been filled from providers
- **THEN** each filled field indicates the provider that supplied its value

#### Scenario: A field the operator typed
- **WHEN** the operator types into a field themselves
- **THEN** it is not attributed to any provider

### Requirement: Suggestion panels start closed during triage
The system SHALL present each note for review with every suggestion panel
closed, showing prefilled values in the fields themselves, so that
reviewing a note does not require scrolling past provider rows.

The operator SHALL be able to open any panel to compare candidates or
re-run a lookup, exactly as in the note editor.

#### Scenario: A note is presented
- **WHEN** a note is presented for review
- **THEN** every suggestion panel is closed

#### Scenario: Opening a panel during review
- **WHEN** the operator opens a suggestion panel on the note under review
- **THEN** it behaves as it does in the editor, including per-provider
  retry and re-running every provider

#### Scenario: Panels do not carry across notes
- **WHEN** the operator opens a panel and then records a verdict
- **THEN** the next note is presented with every panel closed and empty
