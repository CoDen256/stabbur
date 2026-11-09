## 1. Baseline before anything changes

- [x] 1.1 Snapshot current review eligibility *before* touching any rule: per-type counts and the full set of `signature_key`s with `verdict='import'` (7,022 at time of writing). The whole change is judged against this; capture it first or the audit has nothing to compare to.
- [x] 1.2 Record the current verdict-rule histogram alongside it, so a rule that shifts for an unrelated reason is distinguishable from this change's effect.

## 2. Type re-routing (design D7)

- [ ] 2.1 `normalize.py`: detect sentence content in a source's single-word field and assign the sentence-shaped type there, not in `judge`. 23 known `core6k` rows (`Hvor er nærmeste sykehus?`, `Jeg lærer norsk.`, `Snakker du engelsk?`, `Tar dere kort?`, `Kan jeg få menyen, takk?`).
- [ ] 2.2 Share the sentence-shape test with task 3.1 — one implementation, so detection and the skip rule cannot drift apart.
- [ ] 2.3 Assert the 23 move from `word` to the sentence type, and that no genuine single-word or expression candidate moves with them.

## 3. The fully-known-sentence rule (design D1, D2)

- [ ] 3.1 Sentence-shape test: initial capital **required**, with sentence punctuation and pronoun/interrogative presence as corroborating signals.
- [ ] 3.2 Skip when every token is known (inflection-closed, via the existing known-token set) **and** the candidate is sentence-shaped.
- [ ] 3.3 **Hard lowercase guard, with its own test** (design D1): a lowercase candidate can never be skipped by this rule, at any token-familiarity level, regardless of note type or word count. Implement as a guard, not as a term inside a scoring expression — it is the one thing preventing this rule from destroying 139 idioms.
- [ ] 3.4 No audio condition by default (design D2 — requiring it drops the rule from 571 to 2). Expose it as configuration so task 5.5's sensitivity line can report both.
- [ ] 3.5 Write a distinct rule name and its evidence (which tokens matched, which were unknown) to `verdict`, so the audit can group by cause.
- [ ] 3.6 Expected: ~571 newly skipped, all capital-initial, overwhelmingly `listening`.

## 4. Proper nouns, nationalities, numerals (design D3)

- [ ] 4.1 Proper noun: Norwegian text and English gloss both capitalised, single token → skip. Expect 186.
- [ ] 4.2 Derived-from-proper-noun: lowercase text, capitalised gloss → skip. Expect 50.
- [ ] 4.3 Pure numeral: the **entire** text is a number expression → skip. Expect 26. **Must match the whole text, never a substring** — an earlier attempt matched any text containing a number word and returned 1,564 hits including `en passkontroll`, because `en` is both "one" and the article.
- [ ] 4.4 Restrict all three to lexical-item candidates. The gloss-capitalisation test over sentences returns 1,194 false hits (`God dag!` → `Good day!`); a sentence-initial capital is not a proper noun.
- [ ] 4.5 Accept the month-name leakage (`januar`, `februar`, `juni`, `kristen`) rather than special-casing it — 262 is small enough that the audit recovers them with a one-line scan (design D3).
- [ ] 4.6 Separate rule names per category, so the audit can show which of the three is responsible.

## 5. The eligibility audit (design D5) — the deliverable

- [ ] 5.1 A command producing the before/after review-eligibility report, diffing task 1.1's baseline against the current state.
- [ ] 5.2 Totals: eligible before → after, with the per-rule contribution to the difference.
- [ ] 5.3 Per rule, every newly-skipped candidate listed with its text, gloss, type and evidence — **readable and grouped**, not an undifferentiated dump. The test is whether a wrong skip stands out the way `bil`/`bo`/`by` did.
- [ ] 5.4 Disagreements section: candidates where a new rule contradicts a recorded decision (design D4). Reported, never acted on.
- [ ] 5.5 Sensitivity line: the same totals with task 3.4's audio condition enabled, so the 571-vs-2 trade-off is visible as evidence rather than asserted in a design doc.
- [ ] 5.6 Recovery path: a newly-skipped candidate can be returned to the queue without re-running earlier stages and without discarding decisions.

## 6. Decision precedence (design D4)

- [ ] 6.1 New skip rules apply only to candidates with no recorded `decision`.
- [ ] 6.2 A candidate carrying a decision stays eligible and decided — a rule may not orphan an accept by silently removing its candidate from the push set.
- [ ] 6.3 Assert across a re-run that every pre-existing decision survives and still resolves to a candidate.

## 7. Push ordering (design D6)

- [ ] 7.1 `push.py`: `ORDER BY` the review ordering key (`merge.order_sort_key`) instead of iterating `accepted` unordered.
- [ ] 7.2 Assert an interrupted-and-resumed push still emits in review order.
- [ ] 7.3 Comment the *reason* at the call site: push order → `notes.seq` → `card_slots` → `Cards[]` introduction order, which `03-data-model.md` forbids ever reordering. A future refactor must not "tidy" this away.

## 8. Tests

- [ ] 8.1 `Jeg er norsk` / `Er du norsk?` / `Han bor i Norge` / `Jeg kommer fra Frankrike` → skipped.
- [ ] 8.2 **Every one of these imports**, as a single regression test — the rule's reason for existing: `gi opp`, `bli klar over`, `bli lei av`, `dø ut`, `legge om`, `bytte ut`, `trekke ut`, `vokse opp`, `grue seg`, `ta hensyn til`, `gå i vasken`, `ta skjeen i en annen hånd`, `få endene til å møtes`, `ta noe for god fisk`, `å gå på tur`, `å ta det med ro`, `i gamle dager`.
- [ ] 8.3 A capitalised candidate with one unknown word imports.
- [ ] 8.4 A fully-known capital sentence **with** audio is skipped (task 3.4's default).
- [ ] 8.5 `en passkontroll` is **not** skipped as a numeral; `tjuefire` and `ni hundre` are.
- [ ] 8.6 `God dag!` is not skipped as a proper noun.
- [ ] 8.7 An accepted candidate that a new rule would skip stays accepted and eligible.
- [ ] 8.8 `Hvor er nærmeste sykehus?` is re-typed and then skipped — the operator's original example, end to end.
- [ ] 8.9 Push order matches review order over a multi-candidate fixture.

## 9. Verification

- [ ] 9.1 Re-run `normalize`→`key`→`judge`→`merge`; confirm `decision` untouched.
- [ ] 9.2 Expected queue: 7,022 → ~6,189 (−571 sentences, −262 proper/numeral). A materially different total means a rule is over-reaching — investigate before accepting it.
- [ ] 9.3 **Read the full newly-skipped list.** This is the task that matters: every bug in this pipeline so far — `_EXCLUDED_PROSE_DECKS`, the `A`-field misreading, `når`/`nå` — surfaced from the operator reading output, never from a test.
- [ ] 9.4 Specifically check for `En god del`-class false skips: capitalised genuine expressions whose words are all known. Measured at 3 queue-wide, all `expression`-typed; confirm the count and inspect each.
- [ ] 9.5 Scan the nationality skips for month names and recover any wanted (design D3's accepted leakage).
- [ ] 9.6 Record the real post-run numbers in design.md, replacing the pre-run measurements (repo convention: correct findings in place).
