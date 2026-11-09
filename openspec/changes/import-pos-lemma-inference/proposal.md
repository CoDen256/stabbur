## Why

`push.py` sends `pos` to stabbur (line 139), and what it sends is mostly
unusable. Measured across the 7,273 `type=word` candidates currently in the
store:

```
valid (canonical Norwegian)    1,114   15%
missing                        3,403
off-vocabulary                 2,756   noun · adjective · preposition ·
                                       determiner · set phrase ·
                                       interjection · pronoun · proper noun
```

The canonical vocabulary is **Norwegian**, six values — `substantiv`,
`adjektiv`, `verb`, `adverb`, `preposisjon`, `konjunksjon` — fixed by
`ui/index.html`'s part-of-speech control and by `tun/docs/03-data-model.md`'s
deck map, which keys `C20`–`C25` on exactly those strings. `noun` is not
`substantiv`. `verb` and `adverb` only work today by the accident of being
spelled identically in both languages.

So **85% of imported word notes would arrive undeckable**, and this is
load-bearing in two places rather than one: Mjølnir's deck assignment reads
`pos`, and `03-data-model.md` defines the `inflections` *shape* per
part-of-speech.

`lemma` is worse: populated on **0 of 9,009** candidates, though the schema
has the field and the note editor already has a "From text" action that
derives it by stripping `å ` (from the `lemma-first-suggestions` change).

Both are highly inferable from data already in the store. Measured, four
signals resolve **5,538 of 7,273 (76%)** with only 38 inter-signal conflicts.

**This gates the push.** Nothing has been written to stabbur yet. Fixing it
now is a mapping table and four rules; fixing it after pushing is ~5,538
notes re-edited by hand in the stabbur editor.

## What Changes

- **A source→canonical part-of-speech mapping.** English and Norwegian
  source vocabularies both normalise onto the six canonical values.
  Source values with no canonical equivalent (`determiner`, `set phrase`,
  `interjection`, `pronoun`, `prefix`) do **not** get a wrong value forced
  onto them — they resolve to no part of speech, or to one the other signals
  supply.
- **Four inference signals with a fixed precedence**:

  ```
  1  inflections shape   the shape IS the part of speech, by definition
                         {article,sg_indef,sg_def,pl_*}        → substantiv
                         {positiv,nøytrum,flertall,komp,super} → adjektiv
                         {infinitiv,presens,preteritum,perf}   → verb
                         {form}                                → adverb
  2  text prefix         'å X' → verb · 'en|et|ei X' → substantiv
  3  source word class   mapped as above
  4  translation prefix  'to X' → verb · 'a|an X' → substantiv
  ```

- **Conflicts are surfaced, not silently resolved.** 38 candidates have
  signals that disagree (`substantiv`/`verb` 21, `adjektiv`/`substantiv` 11,
  `adjektiv`/`adverb` 6). They are recorded as conflicts on the candidate,
  the same way cross-source field conflicts already are.
- **`lemma` is derived** for word notes — the headword with any leading
  article or infinitive marker removed, matching what the note editor's
  "From text" action already does, so the two cannot disagree.
- **Non-`word` notes get no part of speech.** The 1,736 `expression` and
  `listening` candidates deck by *type* (`C26`/`C27`), not by part of speech,
  so leaving it unset is correct rather than incomplete.
- **Unresolved stays unresolved.** 1,735 candidates (24%) end with no part of
  speech, and that is reported plainly rather than defaulted to
  `substantiv` — a wrong part of speech routes a card to the wrong deck
  permanently, since deck assignment is frozen at mint.

## Capabilities

### Modified Capabilities
- `bulk-import`: normalising and inferring the part of speech and lemma
  written to stabbur, rather than passing source vocabularies through
  unchanged.

## Impact

- **`scripts/import/normalize.py`**: the mapping table, the four inference
  rules, lemma derivation.
- **`scripts/import/merge.py`**: part-of-speech conflicts recorded alongside
  the existing cross-source field conflicts.
- **`scripts/import/push.py`**: unchanged in shape — it already sends `pos`
  and `inflections`; it will now send `lemma` too.
- **Re-runs**: `normalize` → `key` → `judge` → `merge`. `decision` is
  untouched. Shares a re-run with `import-review-web`'s section 1 if both
  land together, which is worth coordinating rather than re-running twice.
- **Expected after the change**: `substantiv` 3,478 · `verb` 1,158 ·
  `adjektiv` 710 · `adverb` 112 · `preposisjon` 67 · `konjunksjon` 13 ·
  unresolved 1,735.
- **Out of scope**: inferring a part of speech for `expression`/`listening`
  notes; calling smia or any provider (the import tool makes no network
  calls except to stabbur's own API); back-filling notes already pushed —
  there are none.
