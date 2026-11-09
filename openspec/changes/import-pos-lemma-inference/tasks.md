## 0. Ordering

- [x] 0.1 **This change gates `push` (section 7 of `bulk-import-anki-csv`).** Nothing has been written to stabbur yet; after a push it becomes ~5,538 notes re-edited by hand. Land it before any push runs.
- [x] 0.2 It re-runs `normalize`→`key`→`judge`→`merge`, the same re-run `import-review-web` section 1 needs. Coordinate so the pipeline is re-run once, not twice.

## 1. Canonical mapping

- [x] 1.1 Mapping table from source vocabularies onto the six canonical values (`substantiv`, `adjektiv`, `verb`, `adverb`, `preposisjon`, `konjunksjon`), as a reviewable data file rather than inline constants — same convention as `denylist.json`.
- [x] 1.2 Cover every value actually present: `noun`→`substantiv`, `adjective`→`adjektiv`, `verb`, `adverb`, `preposition`→`preposisjon`, `conjunction`→`konjunksjon`, `subjunction`→`konjunksjon`, `substantiv`, `proper noun`→`substantiv`.
- [x] 1.3 `determiner`, `set phrase`, `interjection`, `pronoun`, `prefix` map to **nothing** (design D3) — never to a nearest fit. A wrong part of speech is a permanently mis-filed card; an empty one is fixable in the editor.
- [x] 1.4 Assert the mapping's output range is a subset of the six canonical values, so a future addition cannot leak a new off-vocabulary string.

## 2. Inference

- [x] 2.1 Signal 1 — inflection shape (design D1, highest precedence): noun keys `{article,sg_indef,sg_def,pl_indef,pl_def}`, adjective `{positiv,nøytrum,flertall,komparativ,superlativ}`, verb `{infinitiv,presens,preteritum,perfektum}`, adverb `{form}`. These are disjoint per `tun/docs/03-data-model.md`; a note carrying `pl_def` *is* a noun.
- [x] 2.2 Signal 2 — text prefix: `å X`→verb, `en|et|ei X`→`substantiv`.
- [x] 2.3 Signal 3 — the mapped source word class from section 1. Deliberately **third**, not first (design D2): a source label is authoritative about its own taxonomy, not ours.
- [x] 2.4 Signal 4 — translation prefix: `to X`→verb, `a|an X`→`substantiv`. Weakest; English article usage is suggestive, not structural.
- [x] 2.5 Apply in strict precedence order 1→4, first hit wins.
- [x] 2.6 Only `type=word` notes get a part of speech (design's scope note). `expression` and `listening` deck by type (`C26`/`C27`) — leaving it unset is correct, not incomplete.
- [x] 2.7 Unresolved stays unresolved. **No defaulting to `substantiv`** under any circumstance.

## 3. Conflicts

- [x] 3.1 Where two signals imply different parts of speech, apply the higher-precedence value **and** record the disagreement as a conflict on the candidate, reusing `merge`'s existing cross-source conflict mechanism (design D4) so the review UI surfaces it with no new presentation work.
- [x] 3.2 Expect ~38 conflicts: `substantiv`/`verb` 21, `adjektiv`/`substantiv` 11, `adjektiv`/`adverb` 6. A materially different count means a signal changed behaviour.

## 4. Lemma

- [x] 4.1 Derive `lemma` for `type=word` notes: headword minus any leading `en`/`et`/`ei`/`å`.
- [x] 4.2 Use the **same rule** as the note editor's "From text" action (`deriveLemmaFromText`, `/^å\s+/i`, from the `lemma-first-suggestions` change) — design D5. If the two rules diverge, the same note gets different lemmas depending on who touched it last.
- [x] 4.3 No lemma for `expression` notes — there is no single lemma and inventing one fabricates data.
- [x] 4.4 `push.py` sends `lemma` (it already sends `pos`; confirm the payload includes it).

## 5. Tests

- [x] 5.1 Mapping: `noun`→`substantiv`; `proper noun`→`substantiv`; `determiner`→none; output always within the six canonical values.
- [x] 5.2 Precedence: a candidate whose inflection shape says noun and whose source label says adjective resolves to `substantiv` **and** records a conflict.
- [x] 5.3 Each signal in isolation, and a candidate resolvable only by signal 4.
- [x] 5.4 `expression`/`listening` candidates get neither `pos` nor `lemma`.
- [x] 5.5 An unresolvable word candidate ends with `pos` unset — assert it is not defaulted.
- [x] 5.6 Lemma parity: the import's derivation and `deriveLemmaFromText` agree on a shared set of cases, verb and noun.
- [x] 5.7 Corpus-level assertions after re-running: `substantiv` ~3,478, `verb` ~1,158, `adjektiv` ~710, `adverb` ~112, `preposisjon` ~67, `konjunksjon` ~13, unresolved ~1,735 — and **zero** off-vocabulary values remain.
- [x] 5.8 `push` payload carries a canonical `pos` or none, never a source term.

## 6. Verification

- [x] 6.1 Re-run `normalize`→`merge`; confirm `decision` untouched.
- [x] 6.2 Confirm every distinct `pos` value in `candidate` is one of the six canonical values or null.
- [x] 6.3 Spot-check 30 candidates across all four signals, including every one of the ~38 conflicts — they are the cases most likely to be wrong, and there are few enough to read individually.
- [x] 6.4 Record the real post-run distribution in design.md, replacing the pre-run measurements (repo convention: correct findings in place).
