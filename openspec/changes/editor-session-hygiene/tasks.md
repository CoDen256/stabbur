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
      queries. Verified live in a real browser (Claude-in-Chrome) against
      `docker compose up stabbur-backend`: created a `type=word`,
      `pos=verb` note with `text="legge til ekstra"`; "Look up paradigm"
      (inflections) showed the lemma value while "Suggest pronunciations",
      "Suggest translations", and the audio "Suggest" control all showed
      the full `text` value. Also confirmed via a live `curl` of `POST
      /api/enrich/ipa` with a multi-word `text` that smia's `per_word`
      response (the `smia-ipa-multiword-response` dependency) is live.
- [x] 6.2 Manually verify typing in `text` updates `lemma` live, and that
      editing `lemma` by hand stops it being overwritten. Verified live in
      the browser: typing `"legge til"` into `text` populated `lemma` with
      `"legge"` with no action pressed; hand-editing `lemma` to
      `"legge-override"` and then appending `" ekstra"` to `text` left
      `lemma` unchanged at `"legge-override"`.
- [x] 6.3 Manually verify loading a different note re-enables lemma
      syncing. Verified live: after overriding `lemma` on one note and
      saving it, opening a fresh "+ New note" and typing `"bygge opp"`
      synced `lemma` to `"bygge"` with no override — the prior note's dirty
      flag did not carry over.
- [x] 6.4 Manually verify saving a new note and returning to the form
      leaves every field, query, and pending audio empty. Verified live:
      saved the test note as a draft, clicked "+ New note" again, and
      `text`/`lemma`/part-of-speech were all back to blank/default.
- [~] 6.5 Manually verify opening panels on one note then navigating to
      another leaves every panel closed, and that reopening performs a
      fresh lookup rather than showing the first note's candidates.
      Partially verified live: after opening suggest panels on the
      new-note form and saving, the resulting existing-note detail view
      loaded with every panel collapsed (confirmed by screenshot — no
      panel showed the create form's candidates). Did **not** verify the
      existing-note-to-existing-note case specifically (switching between
      two already-saved notes with a panel open on each), since only one
      test note existed in this session's database.
- [x] 6.6 Manually verify `⟳` re-queries every provider with the panel open
      throughout. Verified live: with the inflections panel open (3
      providers configured), clicking the panel-level `⟳` fired 3 new
      `POST /api/enrich/inflections` requests (one per provider, confirmed
      via network-request capture), and the panel stayed open and visibly
      re-rendered in place rather than collapsing.
- [x] 6.7 Manually verify `⟳` on an **unchanged** query actually re-consults
      the provider rather than returning the cached answer — the specific
      failure this change exists to prevent. Check smia's logs or a
      provider-side effect, not just the rendered value, since a correct
      re-run and a cache hit can look identical on screen. Verified live in
      the browser by intercepting `fetch` and inspecting request bodies:
      clicking the panel-level `⟳` with an unchanged query sent
      `"forceRefresh":true` on every provider's request, while a plain
      toggle close+reopen of the same panel (an ordinary open, not a
      re-run) sent no `forceRefresh` key at all — confirming the D5
      distinction end-to-end. Also confirmed via live `curl` and the new
      backend tests that stabbur forwards the flag byte-for-byte and never
      originates it. Did **not** inspect smia's own cache internals/logs to
      confirm it actually re-hits the provider rather than merely accepting
      the flag — that server-side half is still unverified.
- [x] 6.8 Re-run the backend test suite; record the count and whether a
      real Postgres container was used. `routes/enrich.py` is touched, so
      this is not a pure-UI change. 168 passed, 28 skipped, against the
      real `stabbur-postgres` container already running locally (not a
      mocked DB).

**Note on verification**: no frontend test suite exists in this repo.
6.1–6.4, 6.6, and the client-side half of 6.7 were exercised live in a
real browser (Claude-in-Chrome) against `docker compose up
stabbur-backend` plus the running smia instance, with a test note created
and then deleted to leave the database clean. 6.5 got partial live
coverage (create→existing-note transition only, not existing→existing).
6.7's server-side cache-bypass behavior inside smia was not independently
confirmed (only that stabbur forwards the flag and smia accepts it without
erroring).

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
