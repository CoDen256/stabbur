## Context

Measured against `import/candidates.db` (7,022 candidates with
`verdict='import'`) and the real known-set rebuilt from `stock.py`
(8,424 inflection-closed known tokens, 4,882 Norwegian stock lines).

Queue composition:

```
word        5,346        expression    264        listening  1,412
```

The operator's proposed filter, and why it fails:

```
">=5 words AND no audio"                      catches  37 / 7,022

  listening  >4 words: 1,133   with audio 1,124   without   9
  word       >4 words:    12   with audio    6    without   6
  expression >4 words:    22   with audio    0    without  22
```

Long sentences have audio. The operator's own example also evades it on two
counts: `Hvor er nærmeste sykehus?` is **4 words** and typed **`word`**, not
`listening`, because `core6k`'s `Norwegian-Word` field sometimes holds a
sentence. 23 such rows exist (`Jeg lærer norsk.`, `Snakker du engelsk?`,
`Tar dere kort?`, `Kan jeg få menyen, takk?`).

The signal that does work, and its split by initial case — the measurement
this entire change turns on:

```
all words already known      total     CAPITAL (w/ audio)   lowercase
  listening                    609      571  (569)             38
  expression                   142        3                   139   ← protect
  word                         122       31                    91
```

## Goals / Non-Goals

**Goals:**
- Stop asking the operator about sentences whose every word they know.
- Never skip a lexeme or idiom, at any level of token familiarity.
- Preserve review order all the way to the device.
- Make the change auditable: a before/after eligibility diff the operator can
  read and act on.
- Leave every already-recorded decision standing.

**Non-Goals:**
- No rule that can skip a lowercase candidate on token familiarity. This is
  absolute, not a default.
- No word-count threshold and no audio-presence requirement as the primary
  test — both were measured and rejected (Context).
- No attempt to separate nationality adjectives from month names (D3's
  accepted leakage).
- No re-deciding, reopening or overriding of decisions already made.
- No change to D13's attestation known-set itself — this adds rules that
  consume it, it does not alter how it is built.

## Decisions

### D1 — The fully-known test applies to compositional content only, and capitalisation is the proxy

```
skip   iff   every token is known   AND   the candidate is sentence-shaped
sentence-shaped  ≡  initial capital  (+ sentence punctuation, + pronoun/
                    interrogative presence as corroborating signals)
```

Alternatives considered: apply the test to everything above a word-count
threshold; apply it to `type=listening` only; apply it to anything without
audio.

Chosen: initial capitalisation, with note type as a secondary signal rather
than the gate.

Rationale, and this is the crux of the change: **`D139` prohibits
token-subset matching because lexeme meaning is non-compositional.**
`bli kvitt` does not mean "become rid"; knowing `bli` and `kvitt` does not
mean knowing `bli kvitt`. But a sentence *is* compositional —
`Jeg kommer fra Frankrike` means exactly the sum of its parts, so knowing
every part is knowing the sentence. The prohibition and this rule are
therefore not in tension; they are the same principle applied to the two
sides of a distinction D139 never had to draw.

Capitalisation is the proxy because, measured, it tracks that distinction
almost perfectly in this corpus: of the 142 fully-known `expression`
candidates, 139 are lowercase, and those 139 are `gi opp`, `bli klar over`,
`bli lei av`, `dø ut`, `legge om`, `bytte ut`, `vokse opp`, `grue seg`,
`ta hensyn til`, `gå i vasken`, `ta skjeen i en annen hånd`,
`få endene til å møtes`, `ta noe for god fisk` — the highest-value items in
the entire import. Of the 609 fully-known `listening` candidates, 571 are
capital-initial and are plain sentences.

Note type alone was rejected as the gate because the 23 mistyped `core6k`
sentences would escape it (and D2 only re-routes the detectable ones), and
because 38 lowercase `listening` candidates are themselves mistyped
expressions (`å gå på tur`, `å ta det med ro`, `i gamle dager`,
`å vaske opp`) that must not be skipped.

**The lowercase exclusion is a safety property, not a tuning parameter.** It
is the single thing standing between this rule and the destruction of the
import's most valuable content, and it should be implemented as a hard guard
with its own test, not as a condition inside a scoring expression.

### D2 — The rule does not require the absence of audio

Operator's framing was "a sentence that has no audio and most likely known".
Measured, the audio condition is destructive:

```
fully-known capital-initial listening:  571 total
                                        569 have audio
                            →  with "no audio" required:  2
```

Rationale: the reason to skip is that the operator already knows every word.
Whether a third party recorded the sentence is independent of that and is not
evidence about their knowledge. Keeping the condition would reduce the rule
to noise.

Implemented as a **configurable** condition, defaulting to off, specifically
so D5's audit can report the queue under both settings and the operator can
overrule this decision from evidence rather than from argument.

### D3 — Proper nouns, nationalities and numerals, by capitalisation agreement

```
proper noun     186   Norwegian text AND English gloss both capitalised,
                      single token        Barcelona · Italia · Roma · Paris
nationality      50   Norwegian text lowercase, English gloss capitalised
                      italiensk · spansk · fransk · amerikansk
pure numeral     26   the WHOLE text is a number expression
                      tjuefire · ni hundre · titusen · tjuesjuende
                      ─────
                 262   (type=word only)
```

An earlier numeral attempt matched *any* text containing a number word and
produced 1,564 hits — including `en passkontroll`, because `en` is both the
numeral "one" and the indefinite article. The rule must therefore match the
**entire** text, not a substring. Recorded because the mistake is easy to
repeat and the false-positive set looks plausible at a glance.

**Accepted leakage**: the nationality signal also catches month names
(`januar`, `februar`, `juni`) and `kristen`. These are not nationalities and
the operator may well want months. Rather than add special cases guessing
which capitalised glosses are "really" proper, they are skipped and reported
in D5's audit, where a one-line scan recovers them. 262 is small enough that
auditing beats cleverness.

Restricted to `type=word`: the same gloss-capitalisation test over
`listening` returns 1,194 hits, almost all of them sentences whose glosses
merely begin with a capital (`God dag!` → `Good day!`). A sentence-initial
capital is not a proper noun.

### D4 — An explicit decision outranks a later auto-skip

A candidate carrying a `decision` is never removed from the operator's record
by a newly-introduced skip rule.

Rationale: `decision` already survives re-runs structurally (task 1.3's
separate table keyed by signature), which protects decisions from being
*erased*. It does not protect them from being *orphaned* — a candidate the
operator explicitly accepted could silently stop being eligible and vanish
from both the queue and the push set, with the accept still recorded against
nothing. That is a rule overruling the operator, which inverts the intended
authority.

So: new rules filter the *undecided*. Anything already decided keeps its
decision and its eligibility, and the audit lists any candidate where a new
rule disagreed with an existing decision — information worth seeing, but not
worth acting on automatically.

### D5 — The eligibility audit is a deliverable, not a log line

A before/after report over review eligibility, which the operator reads to
verify the filters and recover anything wrongly dropped:

```
  totals        eligible before → after, and the delta per rule
  per rule      every candidate newly skipped, grouped by the rule that
                did it, with its evidence
  recoverable   the full newly-skipped list, readable and re-queueable
  disagreements candidates where a new rule contradicts a recorded decision
  sensitivity   the same totals with D2's audio condition on, so the
                571-vs-2 trade-off is visible rather than asserted
```

Rationale: this change removes ~833 candidates from the operator's sight on
the strength of heuristics with measured but imperfect precision. The pattern
across this whole pipeline has been that the operator finds the bugs by
reading output — the `_EXCLUDED_PROSE_DECKS` disaster, the `A`-field
misreading, the `når`/`nå` collision. Every one surfaced from inspection, not
from tests. A filter whose effect cannot be read is a filter whose errors are
invisible, which is exactly the failure mode `D139`'s bias-toward-importing
exists to avoid. Here the bias is deliberately relaxed, so the audit is what
replaces it.

The audit must be *readable*, not a dump: grouped by rule, with text and
gloss, so a wrong skip stands out the way `bil`/`bo`/`by` did.

### D6 — Review order is preserved into stabbur, because it becomes permanent

`push.py` currently iterates `for row in accepted` with no `ORDER BY`.

```
review order (frequency → CEFR → chapter)
  └─ push order
       └─ notes.seq            Sequence("notes_seq"), assigned on insert
            └─ builder mints card_slots in pull order
                 └─ Cards[]    the card INTRODUCTION ORDER on the device
```

`03-data-model.md` is explicit that appending to a published deck's `Cards[]`
is safe while **reordering it is catastrophic** — `PullCounter` is a block
index, so a reorder silently skips cards and corrupts progress. The
consequence is that introduction order is permanent from first publish, and
cannot be corrected by re-sorting afterwards.

So the ordering fix is not cosmetic: the order the operator reviews in is the
order they will learn in, forever. One missing `ORDER BY` discards the
frequency ranking that `import-review-web` exists to establish.

### D7 — Mistyped sentences are re-routed at `normalize`, not special-cased in `judge`

23 `core6k` rows reach `type=word` carrying a whole sentence. They are
re-typed where types are assigned rather than detected again in every
downstream rule.

Rationale: type routing is already `normalize`'s job (task 3.8), and a
sentence typed `word` is wrong for every consumer, not only for this
change's rules — it would also be deck-assigned as a word note by `builder`.
Fixing the type fixes it once. Detection reuses the same sentence-shape test
as D1, so the two cannot drift apart.

## Risks / Open Questions

- **Capitalisation is a proxy, and proxies break on new sources.** It tracks
  compositionality well in *this* corpus because the sources happen to
  capitalise sentences and not idioms. A source that capitalises every entry
  would defeat it entirely — the CSV already capitalises 4 of its 237 rows,
  one of which (`En god del`) is a genuine expression. D5's audit is the
  mitigation; a per-source capitalisation profile would be a stronger one if
  this ever misfires.
- **571 skips rest on the known-set being right.** Every bug found in this
  pipeline so far has been in the known-set, so a fully-known verdict is only
  as good as `stock.py`. The audit lists them for exactly this reason.
- **`En god del`-class false skips** are the specific failure to watch: a
  capitalised genuine expression whose words are all known. Measured at 3
  across the whole queue, all `expression`-typed, so the exposure is tiny —
  but it is nonzero and it is the one case where this rule does the wrong
  thing by design.
- **Open**: whether month names should be exempted from D3's nationality
  rule. Deferred to the audit rather than guessed at.
- **Open**: whether the 38 lowercase `listening` candidates that are really
  expressions (`å gå på tur`, `i gamle dager`) should be re-typed to
  `expression` by D7's mechanism. They are protected either way by D1's
  lowercase guard, so this is a tidiness question, not a correctness one.

## Implementation measurement (tasks 2.3, 4.1-4.6, 6.3, 9.1, 9.5)

**Blocker, same one design.md already records for the pos-lemma-inference
change**: `STABBUR_IMPORT_STOCK_BUNDLE` is unavailable in this checkout, so
`judge` cannot run end to end here — which blocks every number that needs
the real known-token set (the fully-known-sentence rule's corpus-wide
count, task 3.6/9.2/9.3/9.4). Those rules are implemented and unit-tested
against fabricated known-sets (`tests/test_import_review_queue_filters.py`)
rather than left unverified; whoever next has the bundle should re-run
`judge`/`audit.py` to get the real sentence-rule figures.

Everything *not* gated on the known-set was measured directly against the
real bundle:

```
core6k sentence re-routing (task 2.1/2.3):      54   (design's "23" was
                                                       illustrative, not
                                                       exhaustive; 0 of the
                                                       Country model's
                                                       entries moved with
                                                       them — "San Marino"/
                                                       "New Zealand" have
                                                       neither sentence
                                                       punctuation nor a
                                                       pronoun/interrogative
                                                       token, see
                                                       normalize.py)
proper noun (task 4.1):                        185   (design 186)
derived-from-proper-noun (task 4.2):            50   (design 50, exact)
pure numeral (task 4.3):                        25   (design 26)
                                                ───
                                                260   (design 262)
```

Month-name/`kristen` leakage (task 9.5, D3's accepted leakage), read
individually: `januar`, `februar`, `juni`, `september`, `kristen`,
`kristendom` — six, all recoverable one at a time via `cli.py audit
--recover <signature_key>` if the operator wants any of them back.

Decision-precedence (task 6.3): the real store carries 2,589 recorded
decisions. Re-running `normalize`→`key`→`merge` (the parts of the pipeline
that could run without the stock bundle) left all 2,589 resolving to a
candidate under the same `signature_key` — `key`'s signature count itself
dropped from 7,582 to **7,534** (not 7,582 unchanged), because the 54
re-typed core6k sentences are now excluded from the `note_type != 'listening'`
count the same way every other `listening` row already was (`key.py`'s
`DISTINCT_LEXEME_SIGNATURE_EXPECTED` updated accordingly).

The `En god del`-class false-positive check (task 9.4) could only be
partially measured without the known-set: of the real corpus's `expression`
-typed candidates, **13** are sentence-shaped by `normalize.is_sentence_
shaped` (`God dag!`, `Jeg også`, `Hun smiler`, `Hvilken butikk?`, `Hvor da?`,
`Ja, gjerne.`, `Kom, Dina!`, `Ja, naturligvis!`, `Pannekaker, jippi!`, `Hei,
Cecilie!`, `På utedoveggen?`, `God jul!`, `Jeg kan ikke tenke meg å …`) —
design's "measured at 3" additionally requires every word of each to be
known, which needs the stock bundle to confirm.
