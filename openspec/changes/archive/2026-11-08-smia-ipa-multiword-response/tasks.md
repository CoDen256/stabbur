## 1. Read the `mode` discriminator

- [x] 1.1 `ui/ui.js`: in `buildEnrichProviderRow`'s result handler, stop
      treating a missing/empty `body.candidates` as the only success shape
      for `kind === 'ipa'`. Branch on `body.mode` before the existing
      `Array.isArray(body.candidates)` guard, which currently (line ~1386)
      renders "no results" for every `per_word` response.
- [x] 1.2 `ui/ui.js`: treat an absent `body.mode` as `"phrase"` (design D1),
      so a smia predating `a044ac0` still renders.
- [x] 1.3 `ui/ui.js`: confirm the `phrase` arm renders through the existing
      `renderIpaCandidate` path with no behavioural change.

## 2. Per-word rendering

- [x] 2.1 `ui/ui.js`: render `body.tokens` as one group per token, in array
      order, each labelled with `tokens[i].text`.
- [x] 2.2 `ui/ui.js`: render each token's `candidates` through the existing
      `renderIpaCandidate(prefix)` unchanged (design D4) — no second
      candidate renderer.
- [x] 2.3 `ui/ui.js`: render a token with `candidates: []` as present but
      unresolved, in its input position — not omitted, not an error.
- [x] 2.4 `ui/ui.css`: styles for the token-group breakdown within a
      provider row.

## 3. The assembled `joined` string

- [x] 3.1 `ui/ui.js`: when `body.joined` is present, offer a single action
      that writes it into `transcription`.
- [x] 3.2 `ui/ui.js`: when `body.joined` is absent, offer no phrase-level
      fill — and do **not** join `tokens[].candidates` to synthesise one
      (design D2; this is the correctness constraint of this change).
- [x] 3.3 `ui/ui.js` / `ui/ui.css`: present `joined` as assembled from
      single words, visually distinct from a `mode: "phrase"` candidate
      (design D3).

## 4. Confirmed no-ops

- [x] 4.1 Confirm `renderIpaCandidate` needs no change for smia's merged
      varieties: candidates sharing an `ipa` now arrive pre-merged with
      varieties joined by `/` (e.g. `"e/sw"`), and `c.variety` is already
      rendered verbatim at `ui/ui.js:1417`.
- [x] 4.2 Confirm `routes/enrich.py` needs no change: `post_enrich` passes
      smia's body through unchanged, so both arms already reach the browser
      intact.
- [x] 4.3 Confirm no other kind reads `body.candidates` in a way the `/ipa`
      change affects — `tts`, `translations`, `inflections`, and `stt` are
      untouched by smia's `ipa-multiword` work.

## 5. Verification

- [x] 5.1 Manually verify the `phrase` arm is unchanged: a single-word
      query (e.g. `legge`) against `wikipron` renders exactly as before.
- [x] 5.2 Manually verify the `per_word` arm: a multi-word query with no
      whole-phrase entry (reproduction case: `legge til`) renders one group
      per token instead of "no results".
- [x] 5.3 Manually verify a phrase a provider *does* hold whole (smia's own
      spec cites `av og til` in ipa-dict/nb) returns `mode: "phrase"` and
      renders as a flat candidate list, with no token breakdown.
- [x] 5.4 Manually verify a gap token (a phrase containing one word the
      provider lacks) shows that token as unresolved rather than dropping
      it.
- [x] 5.5 Manually verify `joined` appears and fills when every token has
      exactly one candidate.
- [x] 5.6 Manually verify `joined` is **absent** for a phrase with an
      ambiguous or missing token, and that stabbur offers no assembled fill
      in that case.
- [x] 5.7 Re-run the backend test suite. A UI-only change is expected to
      leave it untouched; record the pass/fail count and whether a real
      Postgres container was used, as previous changes in this repo have.

**Note on verification**: this repo has no frontend test suite (no
browser-automation tooling was available in this environment either), but
a live smia became available at `https://coden256.dev/smia` (`.env` updated
with `SMIA_BASE_URL`/`SMIA_AUTH_TOKEN`) mid-implementation. **5.1–5.6 were
verified against it for real**, through the actual production code path:
stabbur's Flask server was run against the real Postgres container, and
`/api/enrich/ipa` was hit directly (confirming `routes/enrich.py`'s
passthrough) for each scenario —
`wikipron`+`legge` (5.1, phrase), `wikipron`+`legge til` (5.2, per_word with
`joined` present), `ipadict`+`av og til` (5.3, phrase held whole),
`wikipron`+`legge xyzqq` (5.4, gap token, `xyzqq` has no wikipron entry),
`nst`+`legge til` (5.6, `legge` resolves to 3 candidates on `nst` so
`joined` is correctly absent). The exact `renderIpaCandidate`/
`renderIpaPerWord` source (not a reimplementation) was then run against
each real response body in a jsdom harness, including clicking every
rendered "Use" button and asserting the `transcription` field's resulting
value — confirming: the phrase arm is byte-for-byte unchanged; the
per-word arm renders one group per token with the gap token shown as "No
entry" rather than dropped; the `joined` row appears and fills correctly
when present (5.2's third Use button wrote `"lêɡːe tɪl"`); and no `joined`
row is ever rendered when the response omits it (5.4 and 5.6 — zero
synthesis from `tokens[].candidates`, confirming D2). 5.7 was actually run:
`.venv/bin/python -m pytest -q` against the real Postgres container at
`localhost:5434` (per `tests/conftest.py`) — 162 passed, 26 skipped, 1
failed. The failure (`test_import_tool.py::test_cli_stub_stage_fails_cleanly_and_logs_failure`)
is pre-existing and unrelated: confirmed via `git stash` that it only fails
against the concurrent, already-modified `scripts/import/stages.py` /
`tests/test_import_tool.py` in the working tree (bulk-import-anki-csv work
in progress), and passes cleanly on `HEAD`. No test in the suite touches
`ui/ui.js` or `ui/ui.css`, consistent with this being a UI-only change.
