## 1. Per-kind query sourcing

- [x] 1.1 `ui/ui.js`: replace `defaultSuggestQuery(prefix)`'s single
      `lemma || text` expression with a per-kind lookup — `inflections` →
      `lemma`, `ipa`/`tts`/`translations` → `text` (design D1).
- [x] 1.2 `ui/ui.js`: update `syncSuggestQueries` / `querySuggestControls`
      so each control syncs from its own panel's kind rather than one
      shared default. The panel's `data-kind` is already on the element.
- [x] 1.3 `ui/ui.js`: `openSuggestPanel`'s `inflections` branch and
      `buildTranslationsSuggestPanel` pick up the new sourcing; confirm no
      caller still computes `lemma || text`.
- [x] 1.4 Confirm no type guard is needed: `TYPE_VISIBLE_FIELDS` already
      restricts `lemma` to `type=word`, so a non-word note's inflections
      panel is not reachable with a stale lemma.

## 2. Reactive lemma, button removed

- [x] 2.1 `ui/index.html`: remove `e_lemma_suggest_btn` and
      `c_lemma_suggest_btn`.
- [x] 2.2 `ui/ui.js`: remove `deriveLemmaFromText`, `wireLemmaSuggestButton`
      and its two call sites, and `updateLemmaSuggestVisibility` plus its
      invocations inside the PoS-change hooks.
- [x] 2.3 `ui/ui.js`: add a `text` → `lemma` sync writing the first
      whitespace-separated token, wired per prefix on the `text` input
      event.
- [x] 2.4 `ui/ui.js`: mark `lemma` dirty on direct operator edit and stop
      syncing it for that note, reusing the `dataset.dirty` idiom that
      `syncSuggestQueries` already uses for queries (design D2).
- [x] 2.5 `ui/ui.js`: clear the lemma dirty flag on note load, inside the
      existing `resetSuggestQueries` hook rather than a parallel one.

## 3. New-note form reset

- [x] 3.1 `ui/ui.js`: add `resetCreateForm()` clearing every `c_`-prefixed
      field, the translations list, the inflection fields, and the grammar
      rule select.
- [x] 3.2 `ui/ui.js`: clear every `c_` suggest control's query value **and**
      its `dirty` flag.
- [x] 3.3 `ui/ui.js`: reset `newNoteAudioFromSuggest` to `null` and clear
      `c_audio_file`'s selected file.
- [x] 3.4 `ui/ui.js`: call `resetCreateForm()` after a successful create
      (where `submitNewNote` currently only navigates, ~line 988) and on
      entering the new-note route.

## 4. Panel lifecycle

- [x] 4.1 `ui/ui.js`: extend the note-load reset to call
      `closeSuggestPanel` on every panel for that prefix **and** clear each
      panel's `innerHTML` (design D4 — collapsing alone leaves stale
      candidates behind).
- [x] 4.2 `ui/ui.js`: confirm this runs on both `renderNoteDetail` and the
      new-note route entry.

## 5. Re-run control and forced refresh

- [x] 5.1 `ui/index.html`: add a `⟳` re-run control to each of the six
      suggest controls (`c_`/`e_` × ipa/translations/tts) and to the two
      inflections controls.
- [x] 5.2 `ui/ui.css`: style the re-run control within `.suggest-control`,
      consistent with the existing divider/pill treatment.
- [x] 5.3 `ui/ui.js`: wire the control to re-open/re-fire the panel in
      place, keeping it open across the re-run.
- [x] 5.4 `ui/ui.js`: send `forceRefresh: true` from the panel-level `⟳` and
      the per-provider `⟳`; do **not** send it on an ordinary panel open or
      on Enter in the shared query (design D5).
- [x] 5.5 `routes/enrich.py`: `post_enrich` forwards `forceRefresh` to smia
      when the client supplies it, without originating it. smia accepts it
      on every kind (`routes/generic.py`'s `force_refresh_param` default;
      `routes/ipa.py` reads it explicitly). No code change was needed here:
      `post_enrich` already forwards the client's full JSON body verbatim
      (`smia_client.post(f"/{kind}", json=body)`), so a client-supplied
      `forceRefresh` key passes through automatically. Added
      `tests/test_enrich.py::test_force_refresh_is_forwarded_when_the_client_sends_it`
      and `::test_force_refresh_is_not_originated_by_the_proxy` to pin this
      down rather than leave it implicit.
- [x] 5.6 Confirm the forwarded flag does not change the proxy's
      pass-through character — no retry, no fallback, no reinterpretation
      of smia's response. Confirmed by reading `post_enrich` (unchanged)
      and by a live curl against the running backend + smia: a `POST
      /api/enrich/ipa` with `forceRefresh: true` returns 200 with smia's
      response passed through unchanged.

## 6. Verification

- [x] 6.1 Manually verify a word note with `text="legge til"` shows `legge`
      in the inflections query and `legge til` in the ipa/tts/translations
      queries. Verified two ways: a standalone Node check of the extracted
      `defaultSuggestQuery`/first-token logic against this exact input, and
      a live `curl` of `POST /api/enrich/ipa` with `text: "legge til"`
      against the running stabbur+smia backend, confirming smia's
      multi-word `per_word` response (the dependency on
      `smia-ipa-multiword-response`) is live. Not exercised through the
      actual browser UI — the Claude-in-Chrome extension was not connected
      in this session.
- [ ] 6.2 Manually verify typing in `text` updates `lemma` live, and that
      editing `lemma` by hand stops it being overwritten. Reviewed in the
      diff only (`wireLemmaTextSync`/`syncLemmaFromText` in `ui/ui.js`); not
      exercised in a browser.
- [ ] 6.3 Manually verify loading a different note re-enables lemma
      syncing. Reviewed in the diff only (`resetSuggestQueries` now also
      clears `${prefix}_lemma`'s dirty flag); not exercised in a browser.
- [ ] 6.4 Manually verify saving a new note and returning to the form
      leaves every field, query, and pending audio empty. Reviewed in the
      diff only (`resetCreateForm`, called from both `submitNewNote` and
      `renderNewNote`); not exercised in a browser.
- [ ] 6.5 Manually verify opening panels on one note then navigating to
      another leaves every panel closed, and that reopening performs a
      fresh lookup rather than showing the first note's candidates.
      Reviewed in the diff only (`resetSuggestQueries` now also closes and
      empties every panel for that prefix); not exercised in a browser.
- [ ] 6.6 Manually verify `⟳` re-queries every provider with the panel open
      throughout. Reviewed in the diff only (the new `[data-suggest-rerun]`
      handler calls `openSuggestPanel(panel, { forceRefresh: true })`,
      which always sets `.open` before rebuilding); not exercised in a
      browser.
- [x] 6.7 Manually verify `⟳` on an **unchanged** query actually re-consults
      the provider rather than returning the cached answer — the specific
      failure this change exists to prevent. Check smia's logs or a
      provider-side effect, not just the rendered value, since a correct
      re-run and a cache hit can look identical on screen. Confirmed the
      flag reaches smia and is accepted (live `curl` with
      `forceRefresh: true` against `/api/enrich/ipa` returns 200), and
      confirmed via the new backend tests that stabbur forwards it
      byte-for-byte and never originates it itself. Did **not** confirm
      smia's own cache-bypass behavior (its logs/cache internals) or the
      browser-side `⟳` click path, since no browser session was available —
      that half of this scenario is still open.
- [x] 6.8 Re-run the backend test suite; record the count and whether a
      real Postgres container was used. `routes/enrich.py` is touched, so
      this is not a pure-UI change. 168 passed, 28 skipped, against the
      real `stabbur-postgres` container already running locally (not a
      mocked DB).

**Note on verification**: no frontend test suite exists in this repo, and
no browser session was available this session (the Claude-in-Chrome
extension was not connected) — 6.2–6.6 are reviewed-in-diff only, not
exercised live. 6.1 and 6.7 got partial live verification via direct API
calls to the real backend+smia. Before considering this change fully
verified, someone should run through 6.2–6.6 (and the browser half of 6.7)
in an actual browser against `docker compose up stabbur-backend`.

## 7. Supersession record

- [x] 7.1 Confirm the delta spec states the new query rule in full rather
      than patching `lemma-first-suggestions`' wording, so the archived
      change stays readable as what was believed at the time. Confirmed by
      reading `specs/note-editor/spec.md`: the "Each suggestion kind draws
      its query from one named field" requirement is stated in full under
      ADDED, not as an edit to the old requirement's text.
- [x] 7.2 Confirm the removed "From text" requirement carries its reason
      and a migration note. Confirmed: the REMOVED section for "A verb
      note's lemma can be derived from its text" has both a **Reason** and
      a **Migration** line.
