## 1. Proxy the new kind

- [x] 1.1 `routes/enrich.py`: add `"examples"` to `ENRICHABLE_KINDS`.
- [x] 1.2 Update the tuple's adjacent comment — it currently explains the
      `/stt` exclusion in terms of "no corresponding note field today";
      note that `examples` qualifies because `context_text` is that field.
- [x] 1.3 Confirm no new route is needed: `post_enrich` forwards any listed
      kind to `POST /<kind>` generically (design D1).

## 2. Request shape

- [x] 2.1 `ui/ui.js`: `enrichRequestFields` gains an `examples` branch
      sending `{text, lang, limit}`, with `lang` via the existing
      `smiaLangCode` mapping (`no` → `nb`).
- [x] 2.2 `ui/ui.js`: query sources from `text`, consistent with every
      non-inflection kind (design D2).
- [x] 2.3 `ui/ui.js`: send an explicit `limit`, defaulting to smia's own
      default of 3.

## 3. Panel and candidate rendering

- [x] 3.1 `ui/index.html`: suggest control + panel markup beside
      `context_text` on both the `c_` and `e_` forms, matching the existing
      pill structure.
- [x] 3.2 `ui/ui.js`: route `examples` through `openSuggestPanel`'s generic
      per-provider-row path with its own candidate renderer.
- [x] 3.3 `ui/ui.js`: candidate renderer writes the chosen sentence into
      `context_text` on "Use".
- [x] 3.4 `ui/ui.js`: show `sense` and `source` only when the provider
      reports them — no placeholder for an absent field (design D3).
- [x] 3.5 `ui/ui.css`: sentence-length candidate layout — text on its own
      line above the metadata and action, rather than the single-row layout
      the short-value kinds use (design D5).

## 4. Candidate count control

- [x] 4.1 `ui/index.html` / `ui/ui.js`: a control to raise the requested
      count, clamped to smia's 1–10.
- [x] 4.2 `ui/ui.js`: changing the count re-runs the lookup. Treat it as a
      fresh lookup — `limit` is part of smia's cache identity, so a higher
      count is a different cache resource, not a widening of the previous
      one (design D4).

## 5. Settings integration

- [x] 5.1 Confirm `examples` appears in the per-kind provider-preference
      list on the settings page with no special-casing — it arrives from
      `GET /providers` like every other kind.
- [x] 5.2 Confirm a primary provider resolves for `examples` through the
      same first-enabled rule.

## 6. Verification

- [x] 6.1 Verify a request for `examples` is no longer rejected with a 400
      by `post_enrich`.
- [x] 6.2 Verify a dictionary provider (`ordbokene` or `kaikki`) returns
      candidates carrying a `sense`, and that it is displayed.
- [x] 6.3 Verify a corpus provider (`tatoeba` or `leipzig`) returns
      candidates carrying a `source`, and that it is displayed.
- [x] 6.4 Verify a candidate with neither field shows just the sentence,
      with no empty label.
- [x] 6.5 Verify an inflected-form match works end to end — smia's corpus
      providers expand forms, so querying `bok` should be able to return a
      sentence containing `bøker`.
- [x] 6.6 Verify "Use" writes the sentence into `context_text` on both the
      new-note and existing-note forms.
- [x] 6.7 Verify raising the count returns more candidates.
- [x] 6.8 Verify no translation is shown or requested for any example.
- [x] 6.9 Look at panel height with four providers × 3 multi-line
      sentences on the existing-note form, where `context_text` sits low in
      the layout (design Risks).
- [x] 6.10 Re-run the backend suite; `routes/enrich.py` is touched, so
      record the count rather than treating this as UI-only.

**Note**: an unimported corpus provider answers with an empty candidate
list rather than an error, which is indistinguishable on screen from "no
examples for this word". If 6.3 or 6.5 returns nothing, check the
provider's record count in `GET /providers` before concluding the lookup
is broken.

**Verification record (2026-11-08):**
- Backend suite: `env -u DATABASE_URL python -m pytest -q` → 185 passed, 28
  skipped, 0 failed.
- Live-verified in-browser (rebuilt `stabbur-backend` container) against
  the real smia stack (`token: changeme`):
  - `GET /api/enrich/providers` lists `examples: [kaikki, leipzig,
    ordbokene, tatoeba]`.
  - `POST /api/enrich/examples` (`ordbokene`) returns candidates carrying
    `sense`; (`tatoeba`) returns candidates carrying `source` — both
    rendered correctly, each on its own line.
  - `kaikki` returned no entry for "bok" — rendered as an empty-result row
    (`No entry found for "bok".`), not an error; the other three providers'
    rows were unaffected.
  - Querying `text="bok"` returned corpus sentences containing the
    inflected forms `bøker`/`boka` (both `tatoeba` and, after raising the
    count, `leipzig`), confirming smia's inflection-table expansion reaches
    stabbur unmodified.
  - "Use" on a `tatoeba` candidate wrote the sentence into `context_text`
    and marked the row "✓ Used", on the new-note form; the existing-note
    form's panel opens and queries correctly off the saved note's `text`.
  - Raising the count input from 3 to 6 re-ran the lookup and returned 6
    candidates per provider (fresh lookup, not a cache-forced refresh).
  - No translation field appeared in any candidate or request body.
  - Panel height with 4 providers × up to 6 multi-line sentences was tall
    but scrolled normally within the page; no layout breakage.
  - Test note created for verification was deleted afterward.
