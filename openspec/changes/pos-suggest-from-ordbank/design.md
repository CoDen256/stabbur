## Context

The chain already exists end to end and is worth writing down, because the
work here is consuming it rather than building it:

```
smia  adapters/ordbank.py
  oppslag → ordbank_fullform.paradigme_id → ordbank_paradigme.ordklasse
  _SLOT_MAPS[boy_gruppe] = (pos, slot_to_key)
      "substantiv"           → substantiv     ← canonical already
      "verb, normal"         → verb
      "verb, s-verb"         → verb
      "adjektiv"             → adjektiv
      "adjektiv, ulik m/f"   → adjektiv
      "adjektiv, adverbtype" → adverb
      "adverb"               → adverb
  _pos_for(ordklasse)  → first ORDKLASSE token, for classes with no
                         inflection shape: prep · konj · sbu · pron · det ·
                         interj · symb · forkorting
  returns {"lemma", "pos", "paradigm"}

stabbur  ui.js
  2114  renders  `${c.lemma} · ${c.pos}`        ← already visible
  2101  INFLECTION_ROW_GROUPS[c.pos]            ← already used for grouping
  2036  orderedParadigmEntries(c.pos, …)        ← already used for ordering
   448  updateEditInflectionFields(pos, values)
          shapedPos = INFLECTION_SHAPES[pos] ? pos : null
          field block display = shapedPos ? 'block' : 'none'
```

So `pos` is already fetched, already rendered, already load-bearing for how
the panel lays itself out — and never written to the note.

The gap is measured: of the 1,729 word candidates the offline rules leave
unresolved, ~1,266 are single content words (`hallo`, `seks`, `langt`,
`unnskyld`, `greide`, `begge`, `seint`, `ni`, `ti`, `åtte`) — exactly the
function words, numerals and interjections Ordbank is authoritative about.

## Goals / Non-Goals

**Goals:**
- Get Ordbank's part of speech into the note with one action.
- Make the paradigm usable on a note that has no part of speech yet.
- Never silently change a part of speech the operator chose.
- Keep every lookup an explicit operator action.
- Add no backend, no endpoint, no smia change.

**Non-Goals:**
- No derivational-suffix fallback here (operator decision). Rule-based
  inference lives in `import-pos-lemma-inference` only; duplicating it in
  the editor would mean two implementations of the same rules drifting
  apart. Ordbank misses compounds, loanwords and proper nouns; those stay
  manual.
- No bulk backfill across all notes. Per-note, operator-driven.
- No automatic lookup on typing — `note-editor`'s existing rule stands.
- No change to the canonical six, and no proposal of a value outside them.
- No change to deck assignment or to `03-data-model.md`.

## Decisions

### D1 — Applying a paradigm sets the part of speech, because otherwise the paradigm is unusable

This is the core of the change and it is a bug fix dressed as a feature.

`pos` gates the inflection fields (`ui.js:448`). The existing spec says a
paradigm key with no matching field offers *"only the copy action."* On a
note with `pos` unset, `INFLECTION_SHAPES[undefined]` is undefined, the
whole field block is hidden, **no** key matches, and therefore every cell in
a correct, complete paradigm is copy-only. The panel shows the operator the
answer and offers no way to use it.

So the apply action must set `pos` first and fill the forms second — not as
a convenience, but because the fields it writes into do not exist until
`pos` is set. Any design that separates them leaves the operator
hand-selecting a part of speech that the panel is simultaneously displaying.

This narrows the existing requirement's "every fill remains an explicit,
per-field operator action" — fills are still explicit, but no longer
strictly per-field. The per-field fill and per-cell copy both remain; this
is an addition, not a replacement.

### D2 — Apply is non-destructive; explicit suggest overwrites

```
whole-paradigm apply   sets pos ONLY when the note has none
pos suggest → "use"    overwrites whatever is there
```

Operator decision, and the asymmetry is principled rather than arbitrary:
the two actions carry different instructions. Applying a *paradigm* is a
request about inflections, where the part of speech is a precondition the
action happens to satisfy — so it must not quietly reinterpret a
classification the operator already made. Asking for a *part-of-speech*
suggestion and pressing "use" is an unambiguous request about the part of
speech itself.

The asymmetry matters because the cost is asymmetric. `pos` determines deck
assignment, `03-data-model.md` freezes a card's deck at mint, and retiring a
mis-filed card means moving it to a disabled deck rather than removing it.
So a silently-overwritten part of speech is not a recoverable edit — it is a
permanently mis-filed card. An action that only fills a blank cannot cause
that; an action the operator explicitly asked for can, and should.

Disagreement is still surfaced: where the note already has a part of speech
and Ordbank reports a different one, the panel shows both rather than hiding
the conflict — consistent with the existing "Providers disagree" scenario,
which surfaces rather than silently picks.

### D3 — Word classes outside the canonical six are reported, never proposed

`_pos_for()` returns raw Ordbank tokens for classes with no inflection
shape. Mapping:

```
prep        → preposisjon
konj, sbu   → konjunksjon
pron, det, interj, symb, forkorting  → no canonical value
```

For the last group the panel shows what Ordbank said (e.g. *"ordbank: pron —
no canonical part of speech"*) and offers no apply action.

Rationale: the canonical six are `substantiv`/`adjektiv`/`verb`/`adverb`/
`preposisjon`/`konjunksjon`, fixed by `03-data-model.md`'s `C20`–`C25` deck
map. There is no deck for a pronoun, determiner or interjection, so no
part-of-speech value would make such a note deckable — proposing the
nearest-looking one would produce a wrong deck rather than a missing one.
Same error asymmetry `import-pos-lemma-inference` D3 settled on, and the
same conclusion: an empty value is visible and fixable, a plausible wrong
one is neither.

Note the operator has separately decided these entries become
`type=expression` on the import side, which decks to `C26` — so the
long-term answer for them is a type change, not a part of speech, and this
panel should not pretend otherwise.

### D4 — Reuse the existing control pattern rather than inventing one

The part-of-speech suggest control is the same combined toggle + live
editable shared query + per-provider rows used by transcription,
translations, audio and inflections (established by
`smia-enrichment-panel` and `lemma-first-suggestions`), and the query
defaults to `lemma || text` like the others.

Rationale: a fifth suggestion surface that looked or behaved differently
would be the only inconsistent one, and the existing pattern already solves
the query-visibility and retry problems. There is no new interaction model
to design here.

### D5 — No backend work, because the field is already arriving

`routes/enrich.py` already proxies `inflections` and the response already
carries `pos`. The change consumes a value that is already fetched and
already rendered. Recorded explicitly so nobody adds an endpoint for data
that is in hand.

## Risks / Open Questions

- **Ordbank's coverage of the actual gap is unmeasured.** The ~1,266 target
  words look like exactly what Ordbank is good at (function words,
  numerals, interjections), but no query has been run against the real
  table — there is no running Postgres in this environment to test with. It
  could be materially lower for loanwords and compounds. Worth measuring
  before assuming the gap closes.
- **Ordbank's over-expansion is a known hazard.** `tun/docs/07-decisions.md`
  D137 records `ordbank_fullform`'s lemma grouping over-expanding for
  `fort`, which shares a `lemma_id` with the irregular verb `fore`/`forte`.
  A surface form that resolves to several lemmas may report several parts of
  speech; the panel must show the candidates rather than picking one, which
  the existing multi-candidate rendering already does.
- **Inflected forms as note text.** Several unresolved notes are conjugated
  forms rather than lemmas (`er`, `heter`, `kommer`, `bor`, `greide`).
  Ordbank will classify them correctly as verbs, but the note's `text` is
  still a wrong headword — the real fix is `lemma`/`text`, not `pos`, and
  this change will happily set a correct part of speech on a badly-formed
  note. Not made worse here; worth knowing it is not solved either.
- **Open**: whether applying a paradigm should also set `lemma` from the
  same response. The response carries it, `lemma-first-suggestions` already
  made `lemma` the default suggestion query, and 0 of 9,009 imported
  candidates have one — so the case is strong, but it was not asked for and
  adding it silently would widen the action's blast radius beyond what D2
  reasons about.
