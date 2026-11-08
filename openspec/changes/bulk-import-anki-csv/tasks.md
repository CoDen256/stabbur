## 0. Prerequisite

- [x] 0.1 `note-origin-provenance` is implemented and merged — `POST /api/notes` must accept `origin=import` + `import_ref` before stage 6 can run. Stages 1–5 can be built against it unmerged.

## 1. Tool skeleton and candidate store

- [x] 1.1 Create the tool under `scripts/import/` — a CLI with one subcommand per stage (`ingest`, `normalize`, `key`, `judge`, `merge`, `review`, `push`) plus `status`. Not wired into `app.py`; nothing added to `compose.yaml`.
- [x] 1.2 SQLite candidate store at `import/candidates.db` (already gitignored via `/import`). Schema: `run`, `raw_note`, `normalized`, `signature`, `verdict`, `candidate`, `decision`, `log`.
- [x] 1.3 **`decision` is stored in its own table, keyed by lexeme signature — not on `candidate`.** This is what lets `judge`/`merge` be re-run without losing review (design D2). Enforce it: no stage other than `review` may write to `decision`.
- [x] 1.4 Every stage records start/end, counts in/out/discarded, and its `run_id` to `log`. `status` prints the per-stage state so an interrupted run is legible.
- [x] 1.5 Each stage is idempotent: re-running replaces only its own output table for that run, never a prior stage's and never `decision`.

## 2. Ingest (verbatim)

- [x] 2.1 `.apkg` reader: open as zip, read `collection.anki21` (all four are legacy plain SQLite — confirm, do not assume), decode `notes.flds` on `\x1f`, resolve the note type from `col.models` to get field names.
- [x] 2.2 Media mapping: parse the `media` JSON (numeric key → original filename) to resolve `[sound:...]` references to archive members.
- [x] 2.3 Per-source field mapping into `raw_note`, preserving original values untouched:
  - NTNU — `Audio, Article, Word, Transcription, Inflection, English` (749)
  - A1 31k — `Front, Back, Notes, Level, Audio 1` (3,097)
  - core6k — `Norwegian Core` + `Country` models only (6,383); **exclude the `Grammar` model** (225, design D9)
  - freq6k — `6000 Most Frequent Norwegian Words` model only (3,881; design.md's 3,882 was the deck total including the 1 `Read me` note); exclude the `Read me` model
- [x] 2.4 CSV reader for the seven `Her-på-berget` chapter exports: skip blank rows; a row with only column 0 populated is a section header to carry down; `Kapittel` values are not all numeric (`11 Ord og begreper` exists) — do not parse them as ints.
- [x] 2.5 Assert expected row counts per source at the ingest boundary (749 / 3,097 / 6,383 / 3,881 / 1,152) so a parser regression fails loudly rather than silently importing less.

## 3. Normalize

- [x] 3.1 CSV notation parser (design D11, must run before type routing): `/en` `/et` `/ei` gender markers (372 rows), `/-dde`-style past suffixes (100), `(fastsatte)`-style irregulars (80), `a/b` alternate forms (22), `noe`/`noen` complement placeholders (17).
- [x] 3.2 Assert the notation parser moves the CSV from 259/893 to 826/326 single/multiword (corrected from design.md's 816/336 — see design.md's implementation-correction note; every individual notation-category count in 3.1 reproduces exactly, the aggregate split does not and couldn't be closed without the original undocumented script).
- [x] 3.3 NTNU `Inflection` parser (comma-separated) into `{article, sg_indef, sg_def, pl_indef, pl_def}`. **Malformed input must surface as a conflict, never be defaulted** — e.g. `arkitekturerarkitekturene` has a missing comma (design D4's silent-corruption risk).
- [x] 3.4 core6k `Inflections` HTML `<table>` parser into the same shape, with the same no-silent-default rule.
- [x] 3.5 freq6k: take `Word class` as `pos` (noun 2,163 / verb 687 / adjective 662 / adverb 128 / preposition 68 / determiner 63 / set phrase 36 / …) and mine the ordbok `Dictionary entry` HTML for inflected forms feeding D4's form→lemma map.
- [x] 3.6 Field mapping to note fields per source, CSV: `Original word`→`text`, `Explanation (en)`→`translations[en]`, `Example (no)`→`context_text`. **`Explanation (no)` and `Example (en)` are dropped entirely** (operator decision) — not stored, not parked.
- [x] 3.7 Transcription: NTNU's `Transcription` (681 of 749 have IPA); A1's `Notes` field only when it is IPA, not when it is a part-of-speech label (52 vs 762 — the field is polymorphic).
- [x] 3.8 Type routing per candidate (design D11): A1 `Front` ≤2 words → `word` (1,624), sentence → `listening` (1,473); CSV genuine multiword → `expression` (326, corrected from design.md's 336 — see 3.2); all others → `word`.
- [x] 3.9 Deferred to task 4.4 (see design.md's implementation-correction note): a meaningful distinct-lexeme count needs the real D3 signature (head lemma + particles + reflexive + complements), which doesn't exist until `key`. A surface-text key measured here either over-merges (article-stripped: 7,706) or under-merges (kept: 10,500) — both 1,400+ away from 9,129 in opposite directions. `normalize` logs the surface-text count for visibility but asserts nothing; 9,129 is validated once `key` computes the real signature.

## 4. Known-set extraction and judging

> **SUPERSEDED by section 4b (design D13).** Tasks 4.1-4.8 below are left in
> place as the record of what was built and what it cost; **do not use them as
> the specification for new work.** In particular **4.7's regression list now
> asserts the wrong answers**: 8 of its cases (`legge til`, `legge seg`,
> `legge merke til`, `legge til noen i kopi`, `bli kvitt`, `bekymre seg`,
> `bestemme seg`, `regne ut`) are attested in stock and must now **skip**, not
> import. An agent that makes 4.7 green as written will drive the output
> further from correct. Use 4b.
>
> Of the code: `stock.py`'s field-role/deck-exclusion machinery is deleted
> (not corrected); `lexeme.py`'s signature builder is retained for merge
> (section 5) but no longer decides skips; `judge.py` is rewritten; the
> deny-list data file is kept but moves in the ladder.


- [x] 4.1 Stock extractor over `~/mjolnir/index.android.bundle.exploded/2113.js` (not present at that literal path on this operator's machine — see design.md's implementation-correction note for the real path and `STABBUR_IMPORT_STOCK_BUNDLE`). **Exclude decks `C2*`** — those cards are stabbur's own P4 seed, not stock (2,801 entries → 11 in `C2*`, not 13 → 2,790 stock cards, not 2,788; corrected, see design.md).
- [x] 4.2 Extract only high-confidence Norwegian positions (design D5): vocabulary headwords, inflection lines, and Norwegian-sentence `N` fields. **Exclude answer and prose fields entirely.** Do not use HTML emphasis markup as a language signal — it was measured to carry none (28% vs 25%). **Corrected after initial implementation** (found by the operator eyeballing `normalized`, not by any test): field-role was first keyed off the card's `A` field, which turned out to be unrelated to language location — ~785 cards (`B01`-`B12`, `A07`, `A10`, `Z01`) were silently excluded entirely, including common known vocabulary (`trene`, `viktig`, `handle`, `hjelp`, ...). Re-implemented per design D5's own stated rule — content-based: does `N`'s first line open with an English instruction/question — with two small scoped exceptions (`B10`/`B11`: no per-card opener at all; `A03`/`A04`/`A06`/`C01`: confirmed grammar-explanation prose, excluded). See design.md's section 4 implementation-correction note.
- [x] 4.3 Hand-written NO/EN homograph deny-list (`and`, `to`, `for`, `man`, `i`, `form`, …) — entries on it can never auto-skip. Keep it as a reviewable data file, not inline constants.
- [x] 4.4 Lexeme signature builder (design D3): `(head_lemma, ordered_particles, reflexive, obligatory_complements)`, using D4's form→lemma map from source inflection data. No smia call anywhere in this tool.
- [x] 4.5 Judge: auto-skip **only** on exact signature match. Implement the prohibition explicitly — no substring, prefix, head-only, or token-subset comparison exists in the code path.
- [x] 4.6 Flag rules, each writing its evidence to `verdict`: same-head-different-particle (→ reference the stock relative, e.g. `legge til` → `cf. å legge til noen i kopi`), all-tokens-known-phrase-unknown, sentence-shaped.
- [x] 4.7 Regression tests on the measured cases from design D3 — these are the whole point of the change and must be asserted, not assumed. **Two of the originally listed cases don't hold against the real stock bundle and are corrected here (see design.md's implementation-correction note); the underlying anti-prefix/anti-substring property they were meant to demonstrate is still covered, by a verified-correct case and a structural test:**
  - `legge til` imports despite stock teaching `legge`, `legge seg`, `legge merke til`, `legge vekt på`, `legge til noen i kopi`, `legge sammen med`
  - `bli kvitt`, `bli klar over`, `bekymre seg`, `bestemme seg`, `bli lei av` all import
  - `gi opp`, `regne ut`, `dø ut`, `legge om`, `bytte ut`, `låne ut`, `finne fram` all import. **`bli med` removed from this list** — stock card `B13004` teaches `å bli med` verbatim, so by the exact-signature-match rule it is correctly auto-skipped, not a false skip.
  - `aleneforsørger` imports (its signature shares no component with any known signature, despite the letter-prefix). **`allerede` removed from this list** — stock card `B09056` teaches `allerede` itself directly (not merely `alle`, which turns out not to be separately known at all), so it is correctly auto-skipped for a real reason unrelated to prefix matching. The no-prefix-matching property itself is additionally covered by a structural test asserting the code path contains no substring/prefix comparison.
  - `and` (duck) is **not** auto-skipped. Measured: with parenthetical asides stripped before tokenizing (task 4.2), "and" does not actually leak into the known-set from the one identified source (`kvitt, kvitt, kvitt (no comparative and superlative)`) — the deny-list is verified as a working safety net (test asserts a denylisted lemma can never produce a skip verdict even when forced into the known-set), not currently load-bearing for this specific word.
- [x] 4.8 Dump the full skipped set to a reviewable log and spot-check it before any push (design's first stated risk — the known-set is the only part that can lose data). **This spot-check, plus the operator's own direct review of `normalized`, caught four real bugs** (see design.md's section 4 implementation-correction note): a leading `en`/`et`/`ei` was being treated as the signature head instead of stripped like `å`; the freq6k paradigm miner's flat form→lemma map let one word's inflected form overwrite a different word's own standalone identity (`når`→`nå`, `lyst`→`lys`, …); parenthetical-stripping added to fix the `and` leak was also discarding C03's `(som om)` in `å late (som om)` as if it were an aside, when it's the verb's own defining complement; and — the largest by far — field-role extraction was keyed off the card's `A` field instead of `N`'s own content, silently excluding ~785 cards' worth of genuinely known vocabulary across a dozen decks. All four fixed; the distinct-lexeme figure in 3.9/4.4 moved from 9,270 (looked plausible, was wrong) to the corrected 7,582, and the measured auto-skip rate moved from 22.2% to 22.7% after the field-role fix.

## 4b. Known-set rebuild under D13 (attestation)

- [x] 4b.1 **Delete, do not fix**, `stock.py`'s `_EXCLUDED_PROSE_DECKS`, `_ALWAYS_MINE_E_DECKS`, the `A`-field role logic and every per-deck special case. D13 requires no knowledge of card structure; leaving any of it in place reintroduces the bug family that produced corrections 1-7. Keep only the `C2*` exclusion (stabbur's own seed) from task 4.1.
- [x] 4b.2 Build the Norwegian lexicon from the **import sources' own** Norwegian fields (`normalized.text`, ~8,026 tokens). The stock bundle contributes nothing to this lexicon — that direction of dependency is what makes the language test independent of stock's structure.
- [x] 4b.3 Line extraction from stock: split on `<br>` only; **remove** inline tags (`<b>`, `<span>`, …) rather than splitting on them. This is load-bearing — splitting fragments English prose into 1-word pieces, and a lone `and` then scores 100% Norwegian because *duck* is in the lexicon. Measured: 4,584 of 6,438 "Norwegian" segments came out 1-2 words under the wrong handling.
- [x] 4b.4 Per-line language score (D13.1): Norwegian when lexicon share is high and English-stopword share is low; lines under 3 words require unanimity. Assert the leakage ceiling on the resulting token set — `the` 0, `is` ≤2, `that` 0, `and` ≤4, `man` ≤7, `a` ≤39.
- [x] 4b.5 `KNOWN_TOKENS` = every token of every Norwegian line, **closed expansively over inflection** (D13.3): if any form attests a lemma, every form of that lemma is known. This inverts how D4's form→lemma map was used — it previously narrowed matching and must now widen it.
- [x] 4b.6 `KNOWN_NGRAMS` = every contiguous word sequence of every Norwegian line, length 2..line length, **no upper cap** (D13.2). The operator's rule covers full sentences and every subset of them; stock's Norwegian text (~3,154 lines) makes this cheap.
- [x] 4b.7 Rewrite `judge`: skip iff (single-word → lemma in `KNOWN_TOKENS`) or (multiword → surface sequence in `KNOWN_NGRAMS`). Nothing else may skip. Keep the explicit structural test that no substring/prefix/head-only/token-subset comparison exists in the skip path.
- [x] 4b.8 Move the deny-list **after** the known-set check (D13.4) — it vetoes weak evidence only and must never override attestation. Verify the 11 entries stock teaches directly (`i`, `to`, `det`, `den`, `er`, `om`, `så`, `men`, `over`, `under`, `for`) now skip, and the 6 it does not (`and`, `man`, `form`, `that`, `a`, `us`) still import.
- [x] 4b.9 Replace 4.7's regression list. Must **skip**: `legge til`, `legge seg`, `legge merke til`, `legge til noen i kopi`, `bli kvitt`, `bekymre seg`, `bestemme seg`, `bli med`, `regne ut`, `allerede`, plus every word from the operator's report — `bare`, `bil`, `bo`, `by`, `den`, `der`, `det`, `hvor`, `i`, `jente`, `men`, `over`, `tirsdag`, `spise`, `vei`, `vente`, `vil`, `koselig`, `to`. Must **import**: `legge an`, `legge om`, `legge ved`, `gi opp`, `dø ut`, `bytte ut`, `låne ut`, `finne fram`, `bli klar over`, `bli lei av`, `aleneforsørger`, `and`, `man`, `form`.
- [x] 4b.10 Assert the subset rule directly: stock's `Vi bor der` makes `vi`, `bor`, `der`, `vi bor`, `bor der`, `vi bor der` all known, and `bo`/`bodde`/`har bodd` known via 4b.5's closure.
- [x] 4b.11 Sentence candidates are **not** force-imported any more. The `sentence-shaped` rule is removed from the skip path — a1_31k's 1,473 sentence candidates are attestation-checked like everything else (23 of them are attested and must skip). `type=listening` routing (task 3.8) is unaffected; this is only about the verdict.
- [x] 4b.12 **Before switching**: 96 signatures skip today via `exact-match` but are **not** attested under D13. Inspect them and record whether they are genuine finds the old extractor got right (→ D13 needs widening) or artifacts of it (→ expected loss). Do not switch over without this written down — it is the one place D13 could be *worse* than what it replaces.
- [x] 4b.13 Re-run `key` + `judge` only. `ingest` and `normalize` (15,262 rows) are unaffected, and `decision` must be untouched — this is the payoff of D2/task 1.3 and is the check that those decisions were implemented correctly.
- [x] 4b.14 Expected funnel after the switch: skip 1,235 → ~1,683 of 9,009 distinct signatures (13.7% → 18.7%), review queue 7,774 → ~7,326. **Do not judge the fix by this delta** — the 73 signatures from the deck-exclusion bug alone are ~1% of the total but are the most elementary words in the language. Judge it by 4b.9 and by re-reading the skipped set (4.8's procedure, which remains in force).

## 5. Merge

- [x] 5.1 Group `normalized` by lexeme signature; one `candidate` per group (design D8). The signature keeps this merge role under D13 — only its *skip* role is superseded.
- [x] 5.2 Field-level priority `NTNU > A1 > core6k > freq6k > CSV`; highest-priority non-empty value wins. No averaging, concatenation or voting.
- [x] 5.3 Retain losing non-empty values on the candidate and flag it conflicted — do not discard them.
- [x] 5.4 Verify against the measured overlap (2,510 lexemes in exactly 2 sources, 733 in 3, 423 in all 4) that merging is happening rather than silently producing duplicates.
- [x] 5.5 Review ordering key (design D7): freq6k `Frequency index` → `CEFR::*` tag → CSV chapter/section. Candidates with no signal sort last.

## 6. Review

- [x] 6.1 Review interface over the candidate store, ordered by 5.5, with accept / reject / edit per candidate. Local only — this is deliberately not in the stabbur UI (design D1).
- [x] 6.2 Each candidate shows: merged fields, source attribution per field, conflicts, verdict + evidence, the stock relative when flagged by 4.6, and whether human audio is attached.
- [x] 6.3 Decisions write only to `decision` (task 1.3), so re-running `judge`/`merge` preserves them.
- [x] 6.4 Resumable: reopening review returns to the queue position, with counts of reviewed/remaining.

## 7. Push

- [x] 7.1 Audio upload first: NTNU (646) + A1 (2,924) only. **Reject core6k `hypertts-*` and freq6k `ordpar-*` entirely** (design D10). Upload as `blob/<sha256>` via the existing blob endpoint; identical recordings across sources collapse to one blob.
- [x] 7.2 `POST /api/notes` per accepted candidate with `status=draft`, `origin=import`, `import_ref={source, source_note_id, run_id}`. **Never `status=ready`**, under any flag or option.
- [x] 7.3 Store the returned note id on the candidate; skip candidates that already have one (design D12 — makes push resumable and the import reversible).
- [x] 7.4 Rate limiting is explicitly not implemented — no provider is called. If a local throttle against stabbur's own API proves necessary, that is an operational detail, not this change's requirement.

## 8. Verification

- [x] 8.1 Dry-run the full pipeline through `merge` with no push; confirm the funnel against design D6's measured figures (~1,563 auto-skip, ~7,566 import) and investigate any material divergence rather than accepting it.
- [x] 8.2 Push a small accepted subset (≤20) to a throwaway stabbur database; verify `origin`, `import_ref`, `status=draft`, audio blob resolution, and that the notes are filterable by `origin=import` in the notes browser.
- [x] 8.3 Interrupt a push mid-run and re-run it; verify no duplicate notes are created.
- [x] 8.4 Re-run `judge` after editing the deny-list; verify review decisions survive and only verdicts change.
- [x] 8.5 Confirm no `type=grammar` note and no `grammar_rule` row is created by any stage (design D9).
- [x] 8.6 Confirm the tool makes no smia request and no outbound network call other than to stabbur's own API.
- [x] 8.7 Record in the design the actual final counts (imported, skipped, audio coverage) once a full run completes — the design's figures are pre-run measurements and should be annotated with outcomes, per this repo's convention of correcting findings in place.

## 9. Open items to resolve during implementation

- [ ] 9.1 Verify A1's audio is genuinely human by listening to a sample (design risk — if synthesised, coverage falls from ~35% to ~8%).
- [x] 9.2 Decide whether the ~1,100 sentence-shaped A1 candidates need near-duplicate detection against each other; lexeme signatures do not apply to sentences. Record the decision either way.
- [x] 9.3 Decide whether freq6k's 3,881 ordbok articles should serve as a general Norwegian lexicon across the whole pipeline rather than only for its own words.
