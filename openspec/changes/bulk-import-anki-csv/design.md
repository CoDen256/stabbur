## Context

Everything below rests on measurements taken against the actual files, not
estimates. The numbers are recorded here because several of them overturned
an earlier, more obvious design.

**Correction (implementation, section 2):** the original pass counted
`freq6k`'s deck total (3,882 notes) and used that figure for the
model-filtered note count too. The deck's 1 `Read me` note is excluded at
ingest (task 2.3), so the real count feeding the rest of the pipeline is
3,881, not 3,882. Updated at every place this count appears below.

**Correction (implementation, section 3):** two more of this section's
measured figures don't reproduce against a parser built strictly from the
rules this document and tasks.md actually write down, and couldn't be
closed without the original (undocumented) script:

- The CSV notation parser (D11, task 3.1) reproduces every *individual*
  category exactly — 372 gender markers, 100 past-suffix, 22 alternate-form
  (`a/b`, including strong-verb principal parts like `drive /drev-drevet`,
  which turned out to be the same notation design's "alternate forms"
  bucket counts), 17 `noe`/`noen` placeholders, and 78 of the stated 80
  parenthetical irregulars (2 — `(eller) ei` and `å ha (lite/mye) å rutte
  med` — have non-trailing parens and are left as literal multiword text
  rather than forced into a shape they don't have). The *aggregate*
  single/multiword split this produces is **826/326**, not 816/336. Every
  task referencing that split (3.2, 3.8, and the `expression` note-type
  count) now uses 826/326.
- The distinct-lexeme count (task 3.9) can't be meaningfully computed at
  the `normalize` stage at all. It needs the real D3 lexeme signature (head
  lemma + particles + reflexive + complements via the form->lemma map),
  which is `key`'s job (task 4.4), not `normalize`'s. A surface-text proxy
  measured two ways: keeping the leading article/infinitive-marker
  (`en`/`et`/`ei`/`å`) gives 10,500 (undercounts merging — "en antropologi"
  and "antropologi" count twice); stripping it gives 7,706 (overcounts
  merging — collapses genuinely distinct homographs). Both are 1,400+ away
  from 9,129 in opposite directions, which is itself evidence this number
  is a property of the signature, not of normalized text. Deferred: 9,129
  is asserted once `key` exists; `normalize` only logs its surface-text
  count for visibility.

**Correction (implementation, section 4):** `key` now exists. Getting to a
trustworthy distinct-lexeme count took three measurements, because task
4.8's own instruction — spot-check the skipped set before trusting it —
caught two real bugs that a single measurement would have hidden:

1. First pass: **9,270**, within 1.5% of this document's 9,129 — looked
   like confirmation. But spot-checking the skipped set (task 4.8) found
   roughly 20% of all auto-skips were wrong: a leading `en`/`et`/`ei` was
   being treated as the signature *head* rather than stripped the way `å`
   already was, so `et år` keyed as `(head="et", complements=["år"])` —
   a different signature from plain `år`, and from `en år`/`ei år` too.
   This inflated the distinct count with spurious article-led duplicates
   of words already counted once.
2. After stripping the leading article like `å` (lexeme.py's
   `_INDEF_ARTICLE_RE`): **7,252**. Correctly collapsed those duplicates,
   but surfaced a second, independent bug: the freq6k paradigm miner's
   flat form->lemma map let one word's inflected form silently overwrite
   a *different* word's own standalone identity — `når` ("when") is also
   `nå`'s ("now") present tense, so `når` was quietly resolving to `nå`'s
   lemma, and candidates literally spelled `når` would have been
   auto-skipped as if they were `nå`. Same failure for `lyst`/`lyse`,
   `lys`/`lys`, and others.
3. After guarding every standalone headword in `normalized` against being
   overwritten by someone else's derived form (`lexeme.
   protected_identities`, used by both `build_lemma_map_from_normalized`
   and the stock C03 bootstrap merge in `key.build_combined_lemma_map`):
   **7,582**, asserted as the final baseline.

7,582 ends up farther from 9,129 than the first (buggy) measurement — that
is the correct outcome, not a regression: the first number was inflated
by exactly the two bugs above, and the true count also absorbs a handful
of irreducible homograph collisions the D3 signature can't distinguish on
its own (`tre` the tree / the numeral "three" / "to step" necessarily
share one signature, since D3 carries no part-of-speech). Both bugs are
exactly the failure mode task 4.8 exists to catch, and catching them is a
better outcome than hitting 9,129 on a flawed first measurement would have
been.

**A third bug, found by the operator's own spot-check rather than by
code review:** the parenthetical-stripping added above to fix the
`and`-leak case was too broad. It also stripped `(som om)` from C03011's
`å late (som om)` ("to pretend"), silently collapsing it into bare
`late` (C03002's own, separately-taught sense) and losing the fact that
stock teaches this as its own distinct, already-known phrase. Parens are
not uniformly asides: in a regular `A=="N"` vocabulary card they are
(`B05`'s `"(comparative and superlative are not in use)"`), but in a
C03 conjugation answer, a parenthetical directly after the infinitive is
the verb's own defining complement, not commentary about it. Fixed by
making `stock._segments` discard parens wholesale only for the `A=="N"`
extraction path; for C03's `E` field the parens characters are removed
but their contents kept as ordinary tokens, so `"å late (som om)"`
becomes the segment `"å late som om"`. Confirmed afterward: `late`,
`late til`, `late etter`, and `late som om` are now all correctly known,
and the `and`/`comparative` leak fix is untouched (it only ever applied
to the other path). This didn't change the measured auto-skip count —
none of the five import sources happens to contain a literal candidate
spelled `late til` or `late som om` — but it was a real correctness gap
in the known-set regardless, exactly the kind task 4.8 is there to catch
before push, not after.

**A fourth, substantially larger bug, found directly by the operator —
not by any of this change's own tests or spot-checks.** Opening
`normalized` and eyeballing it, the operator found dozens of
unremarkable, common words they already knew (`trene`, `viktig`,
`handle`, `hjelp`, `krig`, `natt`, `dele`, `blid`, `igjen`, `gave`, ...)
that never showed up as auto-skipped. Investigation found the root
cause: task 4.2's extraction keyed which field holds Norwegian off the
card's own `A` field (`A=="N"` means mine `N`; otherwise, only deck
`C03` was special-cased). That assumption is simply wrong. `A` turns out
to denote something about the card's own quiz-answer side, unrelated to
language location — confirmed two ways: `A=="N"` cards exist where `N`
opens with an English question (`B09`'s "What is the meaning of X when
it's used as an adverb?"), and `A=="E"` cards exist across roughly a
dozen decks — `B01`-`B12`, `A07`, `A10`, `Z01`, **~785 cards, more than a
quarter of the entire usable stock bundle** — where `N` opens with an
English instruction ("List the four forms for:", "Provide the
comparative and superlative forms of this adjective:", "Translate using
the correct verb tense:") and `E` holds the actual Norwegian answer.
Every one of those 785 cards was being silently excluded from the
known-set in its entirety.

Design D5's own text already states the correct rule — this was an
implementation gap, not a design gap: "if `N` opens with an English
instruction or question, Norwegian lives in `E` and in `N`'s
continuation lines; otherwise `N` itself is Norwegian." Re-implemented
per that description:

- `stock._opens_with_english` — a word-list check on `N`'s first line
  (`what/how/provide/list/translate/...`), replacing the `A`-field check
  entirely.
- When it matches: mine `E` in full, plus `N`'s own continuation (text
  after the first line) — needed for a third shape found along the way,
  `B01`'s pronunciation drills, where `N` carries the instruction *and*
  the real Norwegian examples as continuation, while `E` is English
  phonetic commentary and not Norwegian at all.
- Two decks (`B10`, `B11`, 195 cards, verified 100% `A=="E"`) have no
  instructional opener at all — the instruction lives only in the deck's
  own description, never repeated per card — so they're a small, scoped
  exception mined unconditionally, not a reversion to trusting `A`
  generally.
- Checked against design's own stated validation figures for this exact
  heuristic (5,351 known single tokens, 4,290 known phrases ≤6 words):
  landed at 2,931 / 2,380 — meaningfully higher coverage than before the
  fix, but like several other figures in this change, not an exact
  reproduction of the original undocumented script's output. Every stock
  card now contributes at least one segment in some form, so the
  remaining gap isn't wholesale deck exclusion; it's smaller
  per-card differences this implementation can't fully close.
- This broader extraction also pulled in genuine grammar-*explanation*
  prose (decks `A03`, `A04`, `A06`, `C01` — confirmed by direct content
  inspection: multi-sentence explanations of genders, pronoun tables,
  tone rules, not vocabulary), which also open with an English question
  and would otherwise leak through the same path — design's own excluded
  category ("excluding answer and prose fields entirely"). A ≤6-word cap
  on extracted segments (matching design's own phrase-length boundary)
  catches most of this for free; the 4 decks above are small (35 cards
  total) and unambiguous enough to exclude wholesale rather than build a
  general prose-vs-vocabulary classifier for a long tail of edge cases.

Net effect on the measured funnel: auto-skip moved from 3,381 (22.2%,
the count after the first three corrections) to 3,464 (22.7%) — fewer
candidates now get wrongly presented for re-review of material the
operator already knows, which is the entire point of this change's
known-set.

Two more corrections, this time to task 4.7's worked regression
examples, found by actually running the judge against the real stock
bundle rather than re-deriving it from the earlier prose:

- **`bli med`** is not a "known head, unknown meaning" case — stock card
  `B13004` teaches `å bli med` verbatim. By this change's own
  exact-signature-match rule (D3), a candidate `bli med` is therefore
  correctly auto-skipped, not a false skip. Removed from the "all import"
  list in 4.7.
- **`allerede`** is not merely a coincidental prefix of a known `alle` —
  stock card `B09056` teaches `allerede` itself directly, and `alle` turns
  out not to be separately known in the extracted set at all. So
  `allerede` is correctly auto-skipped too, for a real reason unrelated to
  prefix matching. The anti-prefix-matching property this example was
  meant to demonstrate is still true and still enforced (the only
  known-set lookup is a dict-key equality check on the full signature —
  there is no substring or prefix comparison in the code at all); it's
  covered in 4.7 by `aleneforsørger` (confirmed via direct measurement:
  its signature shares no component with any known signature) plus a
  structural test on the comparison mechanism itself, rather than by this
  specific illustrative pair.
- Separately, the `(eller) ei` → `and` leak in `kvitt, kvitt, kvitt (no
  comparative and superlative)` that motivated the deny-list's `and` entry
  doesn't actually reach the known-set under this implementation —
  parenthetical asides are stripped before tokenizing (task 4.2), which
  removes the one identified leak source before it can produce a known
  signature. The deny-list (task 4.3) is implemented and tested as a
  working safety net regardless — this just means it isn't currently
  load-bearing for this specific word, which is a better outcome, not a
  reason to skip it.

Also, the stock bundle is not at this document's literal
`~/mjolnir/index.android.bundle.exploded/2113.js` path on this operator's
machine — the equivalent file lives at
`~/dev/mjolnir/index.android.bundle.exploded/2113.js` instead.
`stock.py` defaults to the path as originally documented and honours
`STABBUR_IMPORT_STOCK_BUNDLE` as an override, which is how this section
was actually run and measured.

**The five sources** (`import/`, gitignored):

| source | notes | fields | audio | audio verdict |
|---|---|---|---|---|
| NTNU NoW 1 | 749 | `Audio, Article, Word, Transcription, Inflection, English` | 646 mp3, 44/48 kHz, 128–237 kbps, 646 distinct hashes | human |
| A1 Words & Sentences | 3,097 | `Front, Back, Notes, Level, Audio 1` | 2,924 mp3, varied rates, ID3 titles, 22 dup groups | human (collected corpus) |
| Bokmål Core 6k | 6,608 (6,192 Core + 191 Country + 225 Grammar) | `Norwegian-Word, Norwegian-Sentence, English-Word, English-Sentence, Audio, Note, Inflections` | 6,378 `hypertts-*` ogg/mp3 | **machine TTS — rejected** |
| 6000 Most Frequent (Part 1) | 3,882 (3,881 `6000 Most Frequent Norwegian Words` + 1 `Read me`, excluded) | `Frequency index, Norwegian word, Word class, English translation, Dictionary entry` | 31,084 `ordpar-*` mp3, uniformly 24 kHz/48 kbps, single encoder, ~8 per note | **machine TTS — rejected** |
| Her på berget wordlist | 1,152 (1,094 distinct) | `Kapittel, Original word, Explanation (no), Explanation (en), Example (no), Example (en)` | none | — |

Five sources, five mutually incompatible field models. There is no shared
schema to lean on; each needs its own parser.

**The stock bundle** (`~/mjolnir/index.android.bundle.exploded/2113.js`,
not at that literal path on this operator's machine — see the section 4
implementation-correction note below) is the operator's existing
knowledge: 2,801 card entries, of which 11 (not 13 — corrected, section 4)
are stabbur's own P4 seed in decks C20–C29 and must be excluded, leaving
2,790 (not 2,788) stock cards across 44 decks. Note this file is *builder
output*, not pristine stock — the C2x decks are the tell.

**Measured candidate pool**: 9,129 distinct lexemes after normalization
(7,097 single-word, 2,032 multiword), with grammar excluded.

**Cross-source overlap**: 2,510 lexemes appear in exactly 2 sources, 733 in
3, 423 in all 4. Merging is the common case, not the exception.

## Goals / Non-Goals

**Goals:**
- Import the useful content of all five sources without losing hard-won
  items to an over-eager filter.
- Never auto-discard a lexeme the operator does not actually know.
- One candidate per lexeme, with cross-source conflicts visible.
- Pausable, resumable, re-runnable, logged; every judgement traceable to the
  evidence that produced it.
- Correctable after the fact in both directions — a wrongly skipped lexeme
  can be recovered, a wrongly imported one identified.
- Review ordered by usefulness so the operator can stop at any point and
  have gained the most valuable items.

**Non-Goals:**
- Not a service. No HTTP surface in the stabbur app, nothing deployed,
  nothing in `compose.yaml`.
- No network enrichment. smia is not called (operator decision) — therefore
  no TTS, no IPA lookup, no translation lookup, and consequently no rate
  limiting to design. This also means no lemma oracle (see D4).
- No `type=grammar`. Dropped entirely (D9).
- No `type=pronunciation` notes. `transcription` is filled on `word` notes
  where available; creating pronunciation-type notes stays an authoring act
  in stabbur.
- No re-import of the CSVs. One-shot by operator decision; the two
  spreadsheet exports were measured byte-identical in content, so the
  "collaborative" copy has not diverged and is not tracked.
- No `freq6k` Part 2 (operator: Part 1 is enough).
- Not responsible for reaching `status=ready`. The import's review decides
  *inclusion*; stabbur's own review decides *correctness*.

## Decisions

### D1 — The candidate store is local to the tool, not in stabbur's database

Alternatives considered: `import_run` / `import_candidate` tables in
stabbur's Postgres with review in the stabbur UI; writing all ~7,600
candidates directly into `notes` as drafts and reviewing them there.

Chosen: a SQLite file in `import/`, with review in the tool.

Rationale: the operator reviews candidates *before* they become notes. That
ordering is the deciding factor — candidates are not notes, they are
proposals about notes, and half of them will be rejected. Putting 9,129
proposals into `notes` to then delete thousands would pollute stabbur's
permanent-id space (ids are permanent and tombstoned by `notes-schema`,
which is exactly the wrong lifecycle for a throwaway proposal), and would
make `notes` the holding pen for work that has not been decided yet.

Putting the candidate tables in stabbur's Postgres but outside `notes` was
the earlier plan and was rejected once review moved out of stabbur: a schema,
migration, and route surface in a service that would never read them again
after this one-shot import, and which `tun/docs` is explicit should not
accumulate single-purpose tables.

SQLite also gives pause/resume, cheap full-table rewrites between stages, and
inspectability with ordinary tooling, with no migration ceremony.

The cost is that the candidate store is not backed up with stabbur's
database. Accepted: it is reconstructible from the source archives plus the
stage pipeline, and once candidates are pushed, the durable record lives in
`notes.import_ref`.

### D2 — Six stages, each idempotent, each separately re-runnable

```
ingest     source files            → raw_note          (verbatim, per source)
normalize  raw_note                → normalized        (field mapping, notation parsing)
key        normalized              → lexeme signature
judge      signature + known-set   → verdict + evidence
merge      normalized (grouped)    → candidate         (one per signature)
push       accepted candidate      → stabbur note + blob
```

Each stage reads the previous stage's table and writes its own, rather than
mutating rows in place. Re-running a stage replaces its output and nothing
else.

Rationale: this is what makes the process correctable without starting over.
The expensive, slow, irreversible parts (parsing 450 MB of archives,
uploading audio) are separated from the parts most likely to need
adjustment (the known-set extraction, the merge priority). Tuning the
known-set and re-judging must not require re-parsing; changing merge
priority must not require re-judging.

It also means a *bug found after review has begun* can be fixed by re-running
one stage while preserving the operator's accept/reject decisions, which are
stored separately from every derived table.

### D3 — The comparison unit is a lexeme signature; substring matching is prohibited

```
signature = (head_lemma, ordered_particles, reflexive, obligatory_complements)

legge                  → (legge, [],     no,  [])
legge til              → (legge, [til],  no,  [])
legge seg              → (legge, [],     yes, [])
legge til noen i kopi  → (legge, [til],  no,  [noen, i kopi])
```

Four distinct signatures. **Auto-skip requires an exact signature match.**

Prohibited, explicitly: substring matching, prefix matching, head-only
matching, and matching a multiword candidate by any subset of its tokens.

Rationale, measured. Prefix matching was tested and is unusable: 578
single-word candidates "start with" a stock lemma, but the set is dominated
by coincidence — `allerede` starts with the stock lemma `alle` — and is
indistinguishable from the genuine compound case (`alene` → `aleneforsørger`).
There is no threshold that separates them.

Head-only matching was tested and loses real content: 181 particle/reflexive
candidates have a known head but an unknown meaning (`gi opp`, `bli med`,
`regne ut`, `dø ut`, `legge om`, `bytte ut`, `låne ut`, `finne fram`).

Token-set matching was tested and is the worst of the three: 560 multiword
candidates consist entirely of tokens appearing in stock yet are not
themselves taught (`bli kvitt`, `bli klar over`, `bekymre seg`, `bestemme
seg`, `bli lei av`). These are idioms — the single most valuable category to
import, and the one a token filter annihilates.

The stock's own `legge` family confirms the shape of the problem. Stock
teaches `å legge`, `å legge seg`, `å legge merke til`, `å legge vekt på`,
`å legge til noen i kopi`, `å legge til noen i blindkopi`, `å legge sammen
med`. It does **not** teach bare `legge til`. A candidate `legge til` (to
add) must therefore import — while being shown its stock relatives so the
operator can judge instantly.

### D4 — Lemma resolution comes from the sources themselves, not from smia

smia is out of scope, so there is no `/inflect` oracle. Form→lemma mapping is
built from data already on disk:

| source | inflection data |
|---|---|
| `freq6k` | full ordbok dictionary article per word, 3,881 of them (the deck's 1 `Read me` note excluded), plus `Word class` |
| NTNU | `Inflection` field, comma-separated |
| `core6k` | `Inflections` HTML `<table>` |
| CSV | `/et` `/en` `/ei` gender markers (372), `/-dde` past suffixes (100), `(fastsatte)` irregulars (80) |
| stock | inflection lines on vocabulary cards, and `C03`-style tense-exercise answers |

Rationale: the design never needed an oracle to be *correct*, only to be
*tighter*. Every gap in lemma resolution degrades into a missed auto-skip —
the operator reviews a word they already know and rejects it. That costs a
click. The alternative error, a wrongly-resolved lemma causing an auto-skip,
costs a lost word. The architecture is therefore built so all uncertainty
lands on the click side (D6), which is what makes dropping smia acceptable
rather than merely tolerable.

Noted data-quality hazard: NTNU's inflection field is sometimes malformed
(`arkitekturerarkitekturene` — a missing comma), and `core6k`'s is HTML
requiring real parsing into stabbur's `{article, sg_indef, sg_def, pl_indef,
pl_def}` shape. Both must be validated on parse, not trusted — a silently
mis-parsed inflection table is corruption that survives review, because it
looks plausible.

### D5 — All stock content is known, but only unambiguously-Norwegian positions are extracted

The operator knows the entire stock deck in detail, including its sentences,
rules, pronunciation and listening material. There is therefore **no
taught-versus-encountered distinction** and no card-template classification —
an earlier design carried both and they are deliberately removed.

What remains is a narrower, purely mechanical problem: knowing a grammar rule
written in English does not make the English word `and` a known Norwegian
noun (`and` = *duck*). So the known-set must be extracted only from stock
positions that are unambiguously Norwegian.

Two approaches were tested:

- **HTML emphasis markup** — the hypothesis that Norwegian inside English
  prose is wrapped in `<span class="italic">` / `<b class="bold">`.
  **Failed.** Tokens inside emphasis are 28% Norwegian-morphology versus 25%
  outside: no signal. Stock emphasises both languages (`the` appears 34×
  inside emphasis). Rejected.
- **Field-role by card shape** — if `N` opens with an English instruction or
  question, Norwegian lives in `E` and in `N`'s continuation lines;
  otherwise `N` itself is Norwegian. **Works, partially.** Cut English
  leakage roughly tenfold (`the`: 3,944 → 361 occurrences), yielding 5,351
  known single tokens and 4,290 known phrases of ≤6 words.

The residual leak is real and must be handled rather than ignored. It comes
from meaning-questions — B09's *"What is the meaning of trygt?"* has an
English answer in `E`, which the rule wrongly trusts. `and` leaked 62×, so a
candidate `and` (duck) would be wrongly auto-skipped: a **lost word**, the
one error class that is invisible when it happens.

Therefore the auto-skip set is built only from high-confidence positions —
vocabulary headwords, inflection lines, and Norwegian-sentence `N` fields —
**excluding answer and prose fields entirely**, plus a hand-written deny-list
of NO/EN homographs (`and`, `to`, `for`, `man`, `i`, `form`, …). This lowers
auto-skip below the measured 17% and raises review volume. Accepted
deliberately, per D6.

### D6 — All uncertainty resolves toward importing

The invariant: **when any step is uncertain, the candidate is imported and
flagged, never skipped.**

Rationale: the two error directions are not symmetric. A false import costs
one review click and is immediately visible. A false skip silently loses a
word the operator wanted, and — because nothing was created — leaves no
artifact to notice later. Only the first is recoverable by inspection.

This is also what makes the whole design robust to its own weakest parts
(D4's missing oracle, D5's residual leakage): their failures are routed into
the harmless direction by construction.

The measured consequence, on the looser D5 variant:

```
candidates                                     9,129
├─ auto-SKIP  exact signature match            1,563   17%
│     exact phrase/headword  976
│     single token           587
└─ IMPORT as candidates                        7,566   83%
      no evidence — clean                    5,929
      sentence-shaped → listening            1,100
      phrase, all tokens known — flagged       356
      particle/idiom — flagged "cf. stock"     181
```

### D7 — Review volume is managed by ordering, not by filtering harder

Review order: **frequency rank → CEFR band → textbook chapter**, from
`freq6k`'s `Frequency index` (1–6000) and `CEFR::*` tags, and the CSV's
chapter/section position in a real B1 textbook progression.

Rationale: the operator's stated preference is less review, and the tempting
response is a more aggressive filter — which is precisely how `bli kvitt` and
the other 559 idioms get destroyed (D3). Ordering achieves the same practical
goal without that cost: import all ~7,600 as candidates, review the top few
hundred, and leave the remainder sitting enriched, deduped and queued.

This decouples "import everything" from "review everything", which is the
actual requirement. Nothing is lost by stopping early; the queue persists.

### D8 — Merge is one candidate per signature, by fixed priority, with conflicts recorded

Field-level priority, operator-set:

```
NTNU  >  A1 31k  >  core6k  >  freq6k  >  CSV
```

For each field, the highest-priority source that has a non-empty value wins.
Sources are not averaged, concatenated, or voted.

The CSV is **last**, not first. This reverses an earlier assumption that it
was curated operator data: it is a third-party textbook's wordlist that the
operator has not worked through, so it carries no special authority and gets
no exemption from the known-set filter.

When two sources disagree on a field that is already populated, the losing
value is **recorded on the candidate** rather than discarded, and the
candidate is flagged as conflicted. Rationale: a silent merge hides exactly
the information that makes review fast — seeing that NTNU and core6k gloss a
word differently is often the whole reason to look at it.

### D9 — Grammar is dropped entirely; listening is kept

`core6k`'s `Grammar` model (225 notes) maps cleanly onto `type=grammar` plus
225 distinct `grammar_rule` rows — the only content source stabbur has ever
had for `grammar_rule`. It is nonetheless dropped.

Rationale: 0 of the 225 have audio, and `type=grammar` requires audio to
become a Mjølnir card (`A:"E"`, no type-based exception per
`03-data-model.md`). Sentence-length audio cannot practically be produced
later during stabbur editing, whereas a single word or short phrase can.
Importing 225 permanently unvoiceable notes plus 225 `grammar_rule` rows
would add content that can never progress.

`type=listening` is kept despite also being sentence-length, because the A1
deck supplies human audio for its sentences — the blocker is absent there.
The rule is consistent: drop what has no audio *and* no practical path to it.

Consequence to record: `grammar_rule` still has no content source after this
change.

### D10 — Human audio only; blobs are content-addressed

Accepted: NTNU (646) and A1 (2,924). Rejected: `core6k` (`hypertts-*`,
HyperTTS addon output) and `freq6k` (`ordpar-*`, uniformly 24 kHz/48 kbps
mono from a single recent encoder across 31,084 files — a synthesis pipeline
signature, confirmed as TTS by the operator).

Audio is uploaded as `blob/<sha256>`, the same content-addressed path
captures use, so a recording shared between NTNU and A1 collapses to one
blob automatically.

Measured consequence, stated plainly: ~3,232 of 9,129 lexemes get audio
(~35%). With smia out of scope there is no TTS fallback, so roughly 5,900
notes reach stabbur with no audio and **cannot become Mjølnir cards** until
voiced during stabbur editing. This is accepted — stabbur explicitly allows
`ready` without audio, and Mjølnir's eligibility filter is Mjølnir's concern.

### D11 — Type routing is per-note, not per-source

```
NTNU / core6k / freq6k   → word
CSV                      → word, or expression for the 336 genuine idioms
A1 31k                   → word when Front is ≤2 words (1,624)
                           listening when Front is a sentence (1,473)
```

Rationale: `a1_31k` mixes lexemes and full sentences in the same `Front`
field, so no source-level rule can route it. The CSV's shape is also only
visible after notation parsing — `område /et` and `spå /-dde` look multiword
but are single words carrying inflection data. Parsing that notation moves
the CSV from an apparent 259/893 single/multiword split to a true 816/336,
which changes the type of 557 notes. Notation parsing must therefore run
before type routing.

### D12 — Push is idempotent and records the created note id

`push` writes `POST /api/notes` with `status=draft`, `origin=import`, and
`import_ref = {source, source_note_id, run_id}`, then stores the returned
note id back on the candidate.

Rationale: storing the returned id is what makes the import correctable in
the direction the operator asked about — "I imported something I didn't
want". A candidate carrying a note id can be traced to the exact note to
delete; a pushed candidate without one cannot. It also makes `push`
re-runnable: a candidate that already has a note id is skipped, so an
interrupted push resumes rather than duplicating.

`status=ready` is never written, under any circumstance. The import's review
decides inclusion; stabbur's own draft→ready pass decides correctness. These
are different judgements by different criteria and are deliberately not
collapsed.

## Risks / Open Questions

- **The known-set is the only part that can lose data.** D5's residual
  English leakage and D4's incomplete lemma resolution both feed it. Mitigated
  by restricting extraction to high-confidence positions, the homograph
  deny-list, and D6's bias — but the skipped set should be dumped to a
  reviewable log and spot-checked before any push, not trusted blind.
- **A1's audio is assumed human** on filename, bitrate-variance and ID3
  evidence plus the deck's own claim. Not verified by listening. If it turns
  out to be synthesised, audio coverage falls from ~35% to ~8% (NTNU only).
- **NTNU and core6k inflection parsing** is the highest-risk silent
  corruption path (D4). A malformed inflection table reaches `ready` looking
  correct. Parse failures must be surfaced as conflicts, never defaulted.
- **9,129 is a post-normalization count** and depends on the normalization
  rules themselves (article stripping, case folding, notation parsing). A
  normalization bug shifts every downstream number. Worth asserting the
  count at the `normalize` stage boundary as a regression check.
- **Open**: whether the ~1,100 sentence-shaped A1 candidates should be
  deduped against each other for near-duplicates. Lexeme signatures are
  meaningless for sentences; they would need a different comparison
  entirely. Deferred — they are a minority and duplicates there are cheap to
  reject during review.
- **Open**: whether `freq6k`'s ordbok articles should be mined as a general
  Norwegian lexicon for the whole pipeline rather than only for lemma
  resolution of its own 3,881 words. It is the best lexical resource on disk
  and currently underused.
