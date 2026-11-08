## 1. Read the `mode` discriminator

- [ ] 1.1 `ui/ui.js`: in `buildEnrichProviderRow`'s result handler, stop
      treating a missing/empty `body.candidates` as the only success shape
      for `kind === 'ipa'`. Branch on `body.mode` before the existing
      `Array.isArray(body.candidates)` guard, which currently (line ~1386)
      renders "no results" for every `per_word` response.
- [ ] 1.2 `ui/ui.js`: treat an absent `body.mode` as `"phrase"` (design D1),
      so a smia predating `a044ac0` still renders.
- [ ] 1.3 `ui/ui.js`: confirm the `phrase` arm renders through the existing
      `renderIpaCandidate` path with no behavioural change.

## 2. Per-word rendering

- [ ] 2.1 `ui/ui.js`: render `body.tokens` as one group per token, in array
      order, each labelled with `tokens[i].text`.
- [ ] 2.2 `ui/ui.js`: render each token's `candidates` through the existing
      `renderIpaCandidate(prefix)` unchanged (design D4) — no second
      candidate renderer.
- [ ] 2.3 `ui/ui.js`: render a token with `candidates: []` as present but
      unresolved, in its input position — not omitted, not an error.
- [ ] 2.4 `ui/ui.css`: styles for the token-group breakdown within a
      provider row.

## 3. The assembled `joined` string

- [ ] 3.1 `ui/ui.js`: when `body.joined` is present, offer a single action
      that writes it into `transcription`.
- [ ] 3.2 `ui/ui.js`: when `body.joined` is absent, offer no phrase-level
      fill — and do **not** join `tokens[].candidates` to synthesise one
      (design D2; this is the correctness constraint of this change).
- [ ] 3.3 `ui/ui.js` / `ui/ui.css`: present `joined` as assembled from
      single words, visually distinct from a `mode: "phrase"` candidate
      (design D3).

## 4. Confirmed no-ops

- [ ] 4.1 Confirm `renderIpaCandidate` needs no change for smia's merged
      varieties: candidates sharing an `ipa` now arrive pre-merged with
      varieties joined by `/` (e.g. `"e/sw"`), and `c.variety` is already
      rendered verbatim at `ui/ui.js:1417`.
- [ ] 4.2 Confirm `routes/enrich.py` needs no change: `post_enrich` passes
      smia's body through unchanged, so both arms already reach the browser
      intact.
- [ ] 4.3 Confirm no other kind reads `body.candidates` in a way the `/ipa`
      change affects — `tts`, `translations`, `inflections`, and `stt` are
      untouched by smia's `ipa-multiword` work.

## 5. Verification

- [ ] 5.1 Manually verify the `phrase` arm is unchanged: a single-word
      query (e.g. `legge`) against `wikipron` renders exactly as before.
- [ ] 5.2 Manually verify the `per_word` arm: a multi-word query with no
      whole-phrase entry (reproduction case: `legge til`) renders one group
      per token instead of "no results".
- [ ] 5.3 Manually verify a phrase a provider *does* hold whole (smia's own
      spec cites `av og til` in ipa-dict/nb) returns `mode: "phrase"` and
      renders as a flat candidate list, with no token breakdown.
- [ ] 5.4 Manually verify a gap token (a phrase containing one word the
      provider lacks) shows that token as unresolved rather than dropping
      it.
- [ ] 5.5 Manually verify `joined` appears and fills when every token has
      exactly one candidate.
- [ ] 5.6 Manually verify `joined` is **absent** for a phrase with an
      ambiguous or missing token, and that stabbur offers no assembled fill
      in that case.
- [ ] 5.7 Re-run the backend test suite. A UI-only change is expected to
      leave it untouched; record the pass/fail count and whether a real
      Postgres container was used, as previous changes in this repo have.

**Note on verification**: this repo has no frontend test suite, and the
`per_word` arm cannot be exercised without a live smia carrying the
post-`fad6764` `/ipa`. Record explicitly which of 5.1–5.6 were run against
a real backend and which were only reviewed in the diff, rather than
marking them done by inspection.
