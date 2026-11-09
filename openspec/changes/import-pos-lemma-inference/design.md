## Context

Two fields the import writes to stabbur are effectively broken, and both are
cheap to fix only while nothing has been pushed.

**Part of speech.** `push.py:139` sends `fields.get("pos")` straight through.
Its sources are `freq6k`'s `Word class` (3,441 candidates, English:
`noun`/`verb`/`adjective`/`preposition`/`determiner`/`set phrase`/…) and
NTNU (433, Norwegian: `substantiv`). The canonical vocabulary — from
`ui/index.html`'s `c_pos`/`e_pos_select` options and from
`tun/docs/03-data-model.md`'s deck table — is Norwegian and closed:

```
substantiv → C20     adverb      → C23
adjektiv   → C21     preposisjon → C24
verb       → C22     konjunksjon → C25   (konjunksjon + subjunksjon)
```

Measured over 7,273 `type=word` candidates: 1,114 valid, 2,756
off-vocabulary, 3,403 missing. `notes.pos` has no `CHECK` constraint, so
stabbur accepts `noun` happily and the breakage only shows up downstream,
when `builder` cannot assign a deck.

**Lemma.** 0 of 9,009 candidates populate it.

Inference measured over the same 7,273 (pre-implementation estimate):

```
resolved     5,538   76%
unresolved   1,735   24%
conflicts       38   substantiv/verb 21 · adjektiv/substantiv 11
                     adjektiv/adverb 6
```

**Real post-run measurement (task 6.4, re-run against the full bundle,
stock/known-set judge unavailable in this checkout so these are over all
7,273 `type=word` candidates, not just verdict=import — judge doesn't
filter the `candidate` table, only tags it, so the count is the same
either way):**

```
substantiv    3,485   verb         1,159   adjektiv      694
adverb          115   preposisjon     67   konjunksjon    13
unresolved    1,740   (76.1% resolved)
lemma         7,273   (100% of type=word candidates)
conflicts        34   substantiv/verb 28 · adjektiv/adverb 5
                      adjektiv/substantiv 7
off-vocabulary    0
```

Close to the pre-implementation estimate but not identical — same
"measured, not assumed" convention this change's other figures already
follow (see normalize.py's module docstring). The `substantiv`/`verb`
conflict count (28, not 21) is the only figure with a non-trivial delta;
the other two conflict categories are within a few of the estimate.

This reflects a bug the task 6.3 spot-check caught and fixed before
landing (see task 2.1's code comment in `normalize.py`): the adjective
inflection-shape signal initially included `positiv`/`nøytrum`/
`bestemt_flertall`, which is the exact shape `parse_ntnu_inflection`'s
blank-article branch also produces for an articleless *noun* ("mat",
"smør", "klær") — that branch deliberately leaves `pos` unresolved for
exactly this reason, and the inflection-shape signal was silently
overriding that caution. Fixed by narrowing the adjective shape to the
keys with no such ambiguity (`flertall`/`komparativ`/`superlativ`/
`superlativ_def`); real nouns no longer resolve to `adjektiv`.

## Goals / Non-Goals

**Goals:**
- Every part of speech written to stabbur is from the canonical vocabulary.
- Exploit the signals already present in the store; add no new data source.
- Never guess a part of speech that would route a card to the wrong deck.
- Make disagreement visible rather than arbitrated silently.
- Populate `lemma` consistently with how the note editor derives it.

**Non-Goals:**
- No part of speech for `expression`/`listening` notes — they deck by type.
- No smia call, no network provider. The import tool calls nothing but
  stabbur's own API, and that constraint is not relaxed here.
- No defaulting of unresolved values.
- No `CHECK` constraint added to `notes.pos`. Tempting, but it is a stabbur
  schema change with its own blast radius (the editor permits a custom value
  via `__custom__`), and it belongs in a stabbur change if wanted at all.

## Decisions

### D1 — The inflection shape is the most authoritative signal, because it *is* the part of speech

`tun/docs/03-data-model.md` defines the inflection shapes per part of speech:

```
substantiv  {article, sg_indef, sg_def, pl_indef, pl_def}
adjektiv    {positiv, nøytrum, flertall, komparativ, superlativ}
verb        {infinitiv, presens, preteritum, perfektum}
adverb      {form}
```

These are disjoint. A candidate whose `inflections` carries `pl_def` is a
noun — not probably, definitionally, because that key exists only in the
noun shape. So the shape outranks every other signal including the source's
own label: where NTNU says `substantiv` and the shape says `substantiv` they
agree, and where a source's English label disagrees with the shape, the
shape is right and the label is a mapping artefact.

4,483 of 9,009 candidates have inflections, which is where most of the 76%
comes from.

### D2 — Precedence is fixed and ordered by how much each signal can lie

```
1  inflections shape    cannot be wrong (D1)
2  text prefix          'å ' / 'en|et|ei ' — wrong only if the source
                        mis-formatted its own headword
3  source word class     wrong whenever the source's taxonomy does not
                        match ours (and 5 of its values have no equivalent)
4  translation prefix    weakest — 'a' / 'to' in English glosses are
                        suggestive, not structural
```

Rationale: the ordering is not arbitrary preference, it is ascending
fallibility. Signal 1 is a definitional consequence; signal 4 is a heuristic
over a different language's article usage. Putting the source's own label
*third* rather than first is the counter-intuitive part and the deliberate
one — a source label is authoritative about that source's taxonomy, not
about ours, and `determiner`/`set phrase`/`interjection`/`pronoun`/`prefix`
have no canonical target at all.

### D3 — Unmappable source values resolve to nothing, never to a nearest fit

`determiner` (59), `set phrase` (35), `interjection` (29), `pronoun` (16),
`prefix` (1) have no canonical equivalent among the six.

They are mapped to *no* part of speech, and the other signals get their
chance. They are **not** coerced to the nearest-looking value.

Rationale: deck assignment is permanent. `tun/docs/03-data-model.md`'s
permanence rules freeze a card's deck at mint, and retiring a
mis-assigned card means moving it to a disabled deck, never removing it. So
a wrong part of speech is not a typo to fix later — it is a permanently
mis-filed card. An empty value is visible and fixable in the stabbur editor;
a plausible wrong value is neither.

This is the same asymmetry the known-set work settled on (`D13`/`D139`): the
two error directions have very different costs, so all uncertainty resolves
toward the recoverable one.

### D4 — Conflicts are recorded, not arbitrated

38 candidates have signals that disagree. Precedence technically resolves
every one of them, but silently applying precedence to a genuine
disagreement hides exactly the cases most likely to be wrong.

So the precedence-chosen value is applied *and* the disagreement is recorded
as a conflict on the candidate, using the mechanism `merge` already has for
cross-source field conflicts — which means the review UI surfaces it with no
new presentation work.

### D5 — `lemma` is derived the same way the editor derives it

The headword with any leading `en`/`et`/`ei`/`å` removed.

This is deliberately identical to the note editor's "From text" action
(`deriveLemmaFromText`, from the `lemma-first-suggestions` change, which
strips `/^å\s+/i`). Rationale: if the import derived lemmas by a different
rule than the editor, the same note would get different lemmas depending on
who touched it last, and `notes-read-api` consumers would see churn with no
semantic change.

Scope note: only `type=word` notes get a lemma. `expression` notes have no
single lemma, and inventing one would be fabricating data.

Secondary benefit worth recording: `lemma` is the cleanest possible
similarity signal for the `similar-notes-merge` change, whose morphology
signal currently has low recall precisely because no candidate has a lemma.
The two changes compound; neither depends on the other.

## Risks / Open Questions

- **The 76% figure assumes the inflection parsers are correct.** `normalize`
  task 3.3/3.4 already flag malformed inflection input as a conflict rather
  than defaulting it; a silently mis-parsed shape would now also produce a
  wrong part of speech, so that existing no-silent-default rule becomes
  load-bearing for a second reason.
- **1,735 candidates end with no part of speech** and will reach stabbur
  undeckable. That is the intended outcome (D3), but it means ~24% of word
  notes need a manual part of speech before Mjølnir can use them. Worth
  knowing as a number rather than discovering during review.
- **`notes.pos` is unconstrained**, so nothing prevents a future writer from
  reintroducing `noun`. A `CHECK` constraint would, but it is a stabbur
  change and the editor's `__custom__` option complicates it (non-goal).
- **Open**: whether `set phrase` (35) should instead route to
  `type=expression` rather than being left without a part of speech. It is a
  type signal masquerading as a part-of-speech value, and type routing is
  task 3.8's job, not this change's — but the two interact and nobody has
  looked.
- **A lexeme signature can merge two homographs' inflections across
  sources**, found during the task 6.3 spot-check. `merge.py`'s field
  priority picks `inflections` independently of `text` — for `"tre"`
  (noun: tree/three), NTNU and `freq6k` give it no inflections, so
  `core6k`'s inflections win by default; but `core6k`'s only entry under
  that signature is the *verb* homograph `"å tre"` ("to thread" a
  needle), because `lexeme.py`'s signature strips the infinitive marker
  before keying (pre-existing, `bulk-import-anki-csv` design D3, not
  something this change touches). The candidate ends up with the
  noun's `text` ("tre") but the verb's `inflections`, and signal 1 then
  resolves `pos` to `verb` — wrong, and a conflict is *not* recorded,
  because signal 1 outranks signal 3's (correct) `substantiv` rather than
  merely disagreeing with it as a peer.  Measured: 496 of 7,273 word
  candidates have a different winning source for `text` than for
  `inflections` — an upper bound on exposure, not all of them are
  cross-sense; this specific case was found by inspection, not counted
  exhaustively. Fixing the signature granularity is out of scope here
  (it's `key.py`/`lexeme.py`'s job, not `normalize.py`/`merge.py`'s); worth
  a follow-up change if the review spot-check (task 6.3, in production
  with the real review queue) turns up more than a handful.
