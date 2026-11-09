## Context

`merge` in the import tool already collapsed exact duplicates — one candidate
per lexeme signature `(head, particles, reflexive, complements)`. What it
cannot collapse, by design, is *derivational* relatedness: `å oppleve` and
`en opplevelse` are different lexemes with different signatures, and both are
real rows in the current store.

Measured over the 7,569 `word`/`expression` candidates (`listening` excluded —
trigram similarity over full sentences is noise):

```
trigram threshold sweep, 400-note sample

thresh   mean  median   p90   max   none   >10
  0.3    5.72     4      12    68     7%   16%    too noisy
  0.4    1.76     1       4    20    28%    1%    ← chosen
  0.5    0.57     0       1     6    56%    0%    too strict
  0.7    0.02     0       0     1    98%    0%

oppleve / opplevelse  = 0.583
```

Precision at 0.4, eyeballed on a random sample, is roughly 80% and the
failures are self-evidently wrong (`tur`→`turbo`, `indisk`→`indisium`):

```
anerkjent  → 0.62 å anerkjenne · 0.50 en anerkjennelse
et produkt → 0.64 produktiv · 0.47 produktivitet · 0.46 produksjon
å vedta    → 0.62 et vedtak · 0.40 en vedtekt
passende   → 0.58 upassende                      ← prefix derivation
ned        → nede · nederst · nedi
```

A resource that does **not** solve this: smia's Norsk Ordbank
(`ordbank_lemma`, `ordbank_fullform`, and `adapters/_form_expansion.py`'s
`surface_forms`) is *inflectional*. It expands `oppleve` to
`opplever`/`opplevde`; `opplevelse` is a different lemma entirely. So the
morphology already in the ecosystem is the wrong shape for this problem,
which is why character-level similarity carries the work.

## Goals / Non-Goals

**Goals:**
- Surface related notes while editing or triaging, without being asked twice.
- Make the *reason* for each suggestion visible, since the three signals
  warrant different reactions.
- Let fields be taken individually from a related note — especially audio.
- Make merge structurally incapable of damaging published progress.
- Keep it an on-demand indexed lookup, not a precomputed pair table.

**Non-Goals:**
- No automatic merging, no auto-resolution, no "confidence" threshold that
  acts on its own. Operator decision, explicitly.
- No similarity in the import review tool — stabbur only (operator
  decision). The cost of that is that near-duplicates become notes before
  they can be compared; accepted.
- No `merged_from` provenance field (operator decision — losing the absorbed
  note's `import_ref` is acceptable).
- No cross-`source_lang` similarity. Every note is `no` today and comparing
  across languages is meaningless for these signals.
- No change to the read API, to Mjølnir, or to deck assignment.

## Decisions

### D1 — Three signals, each labelled by what it claims

| signal | mechanism | label | measured |
|---|---|---|---|
| spelling | `pg_trgm similarity(text, …)` ≥ 0.4 | *spelled alike* | mean 1.76/note |
| morphology | two notes' `inflections` share a surface form | *same word family* | 181 shared forms |
| semantics | two notes share a normalised translation | *related, probably not a duplicate* | 848 glosses, 1,879 notes |

Rationale: a single blended score would be worse than any one signal,
because it would erase the distinction the operator acts on. "Spelled alike"
invites a merge; "same word family" nearly guarantees one is wanted;
"related" invites neither. Collapsing them into one number would make the
list feel arbitrary — which is the exact complaint that motivated this
change.

The morphology signal is the highest-precision of the three and the only one
that reliably catches cross-PoS families (`en blogg` / `en blogger` /
`å blogge` all share the form `blogger`; `en kost` / `å koste` share
`koster`). Its recall is low because only 4,483 of 9,009 candidates have
inflections at all. The `article` key must be excluded when comparing — it
holds `en`/`et`/`ei`, which would otherwise match thousands of nouns to each
other.

### D2 — `pg_trgm`, indexed, queried on demand

Alternatives considered: computing trigrams in Python per editor open;
precomputing an all-pairs similarity table; a stemmer-based blocking key.

Chosen: `CREATE EXTENSION pg_trgm` with a GIN index, queried per note.

Rationale: the feature is "show me what's like *this* note", which is a
single indexed lookup, not an all-pairs problem. All-pairs over ~9,000 notes
is ~40M comparisons and would need recomputing on every edit; on-demand is
O(matches). Python-side trigrams would mean pulling every note's text into
the app per editor open.

A stemmer was considered and rejected as the primary mechanism. It matches
`oppleve`/`opplevelse` exactly (both → `opplev`), but it is a blunt
instrument with no score, so it cannot be thresholded or ranked, and
Norwegian suffix stripping is hand-written guesswork. Note the deliberate
contrast with D137 in `tun/docs/07-decisions.md`, which rejected
`to_tsvector('norwegian')` for corpus search: **there the stemmer's
over-aggressiveness was disqualifying because the output was a filter; here
the output is a human-reviewed suggestion list, so a false positive costs a
glance.** Same tool, opposite error tolerance — worth stating so the two
decisions do not read as contradictory.

**Verify `pg_trgm` is present before designing around its absence.** It is
part of contrib and ships with the official `postgres:17-alpine` image, but
that is an assumption until checked against the actual container; the check
costs one query.

### D3 — Status decides the survivor, and that makes merge safe by construction

```
ready  absorbs draft   ✓          draft  absorbs ready   ✗
draft  absorbs draft   ✓          ready  absorbs ready   ✗
```

Operator decision. The property worth recording is what the four rules
*jointly* guarantee, which no single rule states:

```
the absorbed note is always a draft
  → drafts are never returned by notes-read-api (ready-only, D44)
  → therefore no Mjølnir card can have been minted from one
  → the row is hard-deleted per notes-schema's own draft rule
  → deleted_at is never set by a merge; no tombstone is ever created
  → permanence rule 2 (a removed card renders blank) cannot be tripped
```

So **merge requires no knowledge of Mjølnir at all**, which is what keeps
D44/D74's one-directional boundary intact — stabbur still has no idea whether
anything was ever pulled, and does not need to.

This is why "ready absorbs ready" is forbidden rather than merely
discouraged: allowing it would mean tombstoning a note that Mjølnir may hold
a card for, and stabbur structurally cannot know whether it does. A future
change that relaxes this rule reintroduces the entire hazard, so the
invariant is recorded here rather than left implicit in four rows of a table.

The rules are enforced **server-side** in the merge endpoint. The UI should
also not offer a forbidden merge, but the UI must not be the only thing
preventing it.

Side effect, desirable: a `ready` note absorbing a draft bumps `updated_at`,
so `notes-read-api`'s `since` filter surfaces the edit on builder's next pull
(D82). Editing a `ready` note is already explicitly safe — content is
regenerated from current note state on every publish — so nothing extra is
needed.

### D4 — Merge is field-level take, not record replacement

The operator's framing: *"take audio from one, text from the other."* So the
unit of action is a single field, applied into the note currently being
edited, with the absorbed note deleted only once the operator commits.

`audio_blob` is the motivating case and is nearly free: it is a `sha256`, so
taking audio is copying a hash. No blob is moved, copied, or re-uploaded, and
the content-addressed store means two notes referencing the same recording
cost one blob — which is already true of captures.

### D5 — The semantic signal is shown but collapsed

Shared-translation matches are presented in a section collapsed by default,
labelled as related rather than duplicate.

Rationale: measured, this signal groups genuine synonyms far more often than
duplicates — `'connection'` collects `forbindelse`, `en sammenheng`,
`en tilknytning`, `tilkobling`, `et samband`, all of which the operator wants
to learn separately. It is the noisiest of the three and the least
actionable, but it is the only signal that finds relatedness with no spelling
overlap at all, which is information worth having. Collapsed-by-default
resolves that tension without either hiding it or letting it dominate the
panel.

### D6 — No `merged_from` provenance

Operator decision: losing the absorbed note's `import_ref` is acceptable, so
no schema column is added.

Recorded because it is a real, knowing trade-off rather than an oversight:
after a merge, a note whose `origin` is `import`/`core6k` may carry audio
that actually came from `ntnu`, and nothing records that. Since D10's
human-audio rule is the reason audio source matters, the consequence is that
**post-merge audio provenance is not reconstructible.** If that ever becomes
a problem, a `merged_from` JSONB is additive and needs no migration of
existing rows.

## Risks / Open Questions

- **`pg_trgm` availability is assumed, not verified** (D2). Check first; the
  fallback designs are all substantially heavier.
- **Trigram precision is ~80% at 0.4**, eyeballed rather than scored against
  a labelled set. The noise is obvious to a human (`tur`/`turbo`), which is
  why this is acceptable for a suggestion list — but the threshold should be
  revisited once there is real usage, and ideally made configurable rather
  than compiled in.
- **The 0.4 threshold was measured on import candidates, not on `notes`.**
  The distributions should be similar since the text is the same, but the
  measurement should be repeated against the real table once populated.
- **Sentences are excluded** (`type=listening`). If expression notes turn out
  to behave like sentences for similarity purposes, they may need excluding
  too; unmeasured.
- **Open**: `notes.lemma` is populated on 0 of 9,009 import candidates. If it
  were filled (see the `import-pos-lemma-inference` change), same-lemma would
  be a fourth signal — the cleanest of all — and the morphology signal's
  recall would rise sharply. Not a dependency, but the two changes compound.
