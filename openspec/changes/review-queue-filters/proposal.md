## Why

The import review queue holds **7,022 candidates**, and a measurable share of
them are things the operator already knows and should never have been asked
about. The clearest example they raised — `Hvor er nærmeste sykehus?` — is a
sentence whose every word is already taught by the stock deck.

Two filters were proposed and measured. One does not work and one does:

- **">= 5 words and no audio" catches 37 of 7,022.** Long sentences almost
  all *have* audio (1,124 of 1,133 `listening` notes over 4 words). The
  operator's own example is also 4 words long and typed `word`, so the filter
  misses it twice over. Word count and audio are the wrong handles.
- **"every word in it is already known" catches 571**, once restricted
  correctly. Measured against the real known-set (8,424 inflection-closed
  tokens): 609 of 1,412 `listening` candidates have no unknown word at all —
  `Jeg er norsk`, `Er du norsk?`, `Han bor i Norge`, `Jeg kommer fra
  Frankrike`.

The restriction is the whole design. The same test applied to lexemes would
be catastrophic: 139 **lowercase** `expression` candidates are also
"fully known", and they are a catalogue of precisely what the known-set work
exists to protect — `gi opp`, `bli klar over`, `bli lei av`, `dø ut`,
`legge om`, `vokse opp`, `ta hensyn til`, `gå i vasken`, `ta skjeen i en
annen hånd`, `få endene til å møtes`. Initial capitalisation turns out to
track compositionality: a capital-initial sentence means the sum of its
words; a lowercase idiom does not.

Separately, three small things were found while measuring and belong with
this change because they are the same review-quality problem:

- `core6k`'s `Norwegian-Word` field sometimes holds a whole sentence, so 23
  sentences are typed `word` and escape every sentence-aware rule.
- `push.py` iterates accepted candidates with **no `ORDER BY`**, discarding
  the review order. That order is the frequency ranking, and it propagates
  through `notes.seq` to `card_slots` to `Cards[]`, which is the card
  *introduction order* on the device — and `03-data-model.md` forbids ever
  reordering a published deck. Lost here, it cannot be recovered later.
- 262 `type=word` candidates are proper nouns, nationality adjectives, or
  pure numerals.

Above all, the operator needs to be able to **see what the filters removed**,
compare it against what was eligible before, and confirm nothing important was
dropped. That audit is a deliverable of this change, not a side effect.

## What Changes

- **A fully-known-sentence skip rule.** A candidate is skipped when every one
  of its words is already known *and* it is sentence-shaped — which requires
  an initial capital. Compositional content only.
- **Lowercase candidates are never skipped by this rule**, regardless of how
  known their words are. This is the rule's safety property, not a
  refinement: it is what keeps `gi opp` and `bli kvitt` in the queue.
- **The rule does not require the absence of audio.** Requiring it reduces
  the rule from 571 notes to 2, because fully-known sentences overwhelmingly
  have recordings. Knowing every word in a sentence is the reason to skip it;
  whether someone recorded it is not. The condition is **configurable** so the
  audit can report both.
- **Proper nouns, nationality adjectives and pure numerals are skipped** —
  186 + 50 + 26 = 262 `type=word` candidates, detected from
  capitalisation agreement between the Norwegian text and its English gloss,
  and from the text being wholly a number expression.
- **`core6k` sentences mistyped as `word` are re-routed**, so sentence-aware
  rules see them.
- **`push` emits in review order**, by the same ordering key review used.
- **A before/after review-eligibility report** — the audit. Every candidate
  whose eligibility this change alters is listed with the rule that changed
  it and the evidence behind it, so the operator can confirm the filters were
  right and recover anything wrongly dropped.
- **An explicit operator decision outranks a later auto-skip.** A candidate
  the operator already accepted or rejected stays decided; a new rule cannot
  silently remove it from the record.

## Capabilities

### Modified Capabilities
- `bulk-import`: new skip rules over sentence-shaped and proper-noun/numeral
  candidates, type re-routing for mistyped sentences, push ordering, the
  precedence of operator decisions over auto-skips, and the eligibility audit.

## Impact

- **`scripts/import/normalize.py`**: re-route `core6k` sentences mistyped as
  `word`.
- **`scripts/import/judge.py`**: the fully-known-sentence rule, the
  proper-noun/nationality/numeral rules, each writing its own rule name and
  evidence to `verdict` so the audit can group by cause.
- **`scripts/import/push.py`**: `ORDER BY` the review ordering key.
- **New**: an audit command producing the before/after eligibility diff.
- **Re-runs**: `normalize` → `key` → `judge` → `merge`. `decision` is
  untouched, and this change additionally makes that guarantee explicit by
  having decisions outrank new auto-skips.
- **Expected effect**: queue 7,022 → ~6,189, a 12% reduction, of which 571
  are the "I already know all of this" sentences the operator described.
- **Out of scope**: any rule that would skip a lowercase lexeme or
  expression; month names and other capitalised-gloss words that are not
  nationalities (see design D3's stated leakage); re-deciding anything the
  operator has already decided.
