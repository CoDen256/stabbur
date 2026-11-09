## MODIFIED Requirements

### Requirement: Each note is resolved by one of four verdicts
The system SHALL offer, in a fixed position that does not move as the
note's content changes, exactly four actions on the note under review:

- **Accept** — set the note's status to `ready`, saving any edits, and
  advance.
- **Send to back** — return the note to the queue so it is presented again
  only after every other note currently awaiting review.
- **Delete** — delete the note, following the system's existing deletion
  rules, and advance.
- **Skip** — advance, changing neither status nor the note's edited fields.

Whether "Send to back" and "Skip" save the current edits before acting is
governed by the operator's triage-navigation-save preference (see
`operator-settings`): when set to autosave, both save first, exactly as
"Send to back" always has; when set to manual, neither does, matching
"Skip"'s original behavior. The preference applies uniformly to both
actions — there is no way to configure one without the other — because
there is no operator-visible reason the two should ever diverge.

Accepting SHALL be the only action that sets a note to `ready`. Prefilling
or editing a field SHALL NOT advance a note's status on its own. Regardless
of the navigation-save preference, the system SHALL always offer a
separate, explicit Save action (see the new requirement below) that
persists the note under review's current edits without advancing or
changing its status, so the operator can save at will independent of any
verdict.

#### Scenario: Accepting a note
- **WHEN** the operator accepts the note under review
- **THEN** its edits are saved, its status becomes `ready`, and the next
  note is presented

#### Scenario: Sending a note to the back, autosave preference
- **WHEN** the operator sends the note under review to the back, and the
  navigation-save preference is set to autosave
- **THEN** its edits are saved, it is not marked ready, and it is
  presented again only after the rest of the queue

#### Scenario: Sending a note to the back, manual preference
- **WHEN** the operator sends the note under review to the back, and the
  navigation-save preference is set to manual
- **THEN** it is not marked ready and is presented again only after the
  rest of the queue, but any edit since the last explicit save is not
  persisted

#### Scenario: A deferred note's edits survive under autosave
- **WHEN** the navigation-save preference is set to autosave, and the
  operator edits several fields and then sends the note to the back
- **THEN** those edits are present when the note comes round again

#### Scenario: Skipping a note, autosave preference
- **WHEN** the operator skips the note under review, and the
  navigation-save preference is set to autosave
- **THEN** its edits are saved, its status is unchanged, and the next note
  is presented

#### Scenario: Skipping a note, manual preference
- **WHEN** the operator skips the note under review, and the
  navigation-save preference is set to manual
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

## ADDED Requirements

### Requirement: An explicit Save action persists edits independent of any verdict
The system SHALL offer a Save action, bound to the key `m`, that persists
the note under review's current edits via the same path a verdict's own
save uses, without changing its `status` or advancing the queue — so the
operator can save in-progress work and keep reviewing the same note, or
come back to it later with nothing lost.

#### Scenario: Saving without resolving
- **WHEN** the operator edits several fields and then presses Save (or its
  key binding)
- **THEN** those edits are persisted, the note under review does not
  change, its status is unchanged, and the queue does not advance

#### Scenario: Saving is available regardless of the navigation-save preference
- **WHEN** the operator's navigation-save preference is set to manual
- **THEN** the Save action still persists edits on demand — the preference
  only governs whether Send to back, Skip, and Go to previous do so
  automatically

### Requirement: Returning to the previous note respects the navigation-save preference
The system SHALL, when the operator returns to the previously-reviewed note
and the navigation-save preference is set to autosave, save the note being
left before navigating back — the same preference and the same save path
"Send to back" and "Skip" use. Under the manual preference, returning to
the previous note SHALL NOT save the note being left.

#### Scenario: Going back under autosave
- **WHEN** the operator has edited the current note under review, the
  navigation-save preference is set to autosave, and the operator returns
  to the previous note
- **THEN** the current note's edits are persisted before navigating back

#### Scenario: Going back under manual
- **WHEN** the operator has edited the current note under review, the
  navigation-save preference is set to manual, and the operator returns to
  the previous note
- **THEN** the current note's edits since the last explicit save are not
  persisted

### Requirement: The audio suggest panel can attach a chosen candidate directly
The system SHALL let the operator attach a TTS suggest candidate to the
note under review the same way the note editor does, regardless of which
form (triage or editor) presented the candidate.

#### Scenario: Using a TTS candidate during triage
- **WHEN** the operator opens the audio suggest panel on the note under
  review and clicks "Use" on a candidate
- **THEN** the resulting stabbur-stored audio is attached to the note under
  review, exactly as it would be from the note editor
