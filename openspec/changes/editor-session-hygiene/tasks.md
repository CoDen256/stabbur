## 1. Per-kind query sourcing

- [ ] 1.1 `ui/ui.js`: replace `defaultSuggestQuery(prefix)`'s single
      `lemma || text` expression with a per-kind lookup — `inflections` →
      `lemma`, `ipa`/`tts`/`translations` → `text` (design D1).
- [ ] 1.2 `ui/ui.js`: update `syncSuggestQueries` / `querySuggestControls`
      so each control syncs from its own panel's kind rather than one
      shared default. The panel's `data-kind` is already on the element.
- [ ] 1.3 `ui/ui.js`: `openSuggestPanel`'s `inflections` branch and
      `buildTranslationsSuggestPanel` pick up the new sourcing; confirm no
      caller still computes `lemma || text`.
- [ ] 1.4 Confirm no type guard is needed: `TYPE_VISIBLE_FIELDS` already
      restricts `lemma` to `type=word`, so a non-word note's inflections
      panel is not reachable with a stale lemma.

## 2. Reactive lemma, button removed

- [ ] 2.1 `ui/index.html`: remove `e_lemma_suggest_btn` and
      `c_lemma_suggest_btn`.
- [ ] 2.2 `ui/ui.js`: remove `deriveLemmaFromText`, `wireLemmaSuggestButton`
      and its two call sites, and `updateLemmaSuggestVisibility` plus its
      invocations inside the PoS-change hooks.
- [ ] 2.3 `ui/ui.js`: add a `text` → `lemma` sync writing the first
      whitespace-separated token, wired per prefix on the `text` input
      event.
- [ ] 2.4 `ui/ui.js`: mark `lemma` dirty on direct operator edit and stop
      syncing it for that note, reusing the `dataset.dirty` idiom that
      `syncSuggestQueries` already uses for queries (design D2).
- [ ] 2.5 `ui/ui.js`: clear the lemma dirty flag on note load, inside the
      existing `resetSuggestQueries` hook rather than a parallel one.

## 3. New-note form reset

- [ ] 3.1 `ui/ui.js`: add `resetCreateForm()` clearing every `c_`-prefixed
      field, the translations list, the inflection fields, and the grammar
      rule select.
- [ ] 3.2 `ui/ui.js`: clear every `c_` suggest control's query value **and**
      its `dirty` flag.
- [ ] 3.3 `ui/ui.js`: reset `newNoteAudioFromSuggest` to `null` and clear
      `c_audio_file`'s selected file.
- [ ] 3.4 `ui/ui.js`: call `resetCreateForm()` after a successful create
      (where `submitNewNote` currently only navigates, ~line 988) and on
      entering the new-note route.

## 4. Panel lifecycle

- [ ] 4.1 `ui/ui.js`: extend the note-load reset to call
      `closeSuggestPanel` on every panel for that prefix **and** clear each
      panel's `innerHTML` (design D4 — collapsing alone leaves stale
      candidates behind).
- [ ] 4.2 `ui/ui.js`: confirm this runs on both `renderNoteDetail` and the
      new-note route entry.

## 5. Re-run control and forced refresh

- [ ] 5.1 `ui/index.html`: add a `⟳` re-run control to each of the six
      suggest controls (`c_`/`e_` × ipa/translations/tts) and to the two
      inflections controls.
- [ ] 5.2 `ui/ui.css`: style the re-run control within `.suggest-control`,
      consistent with the existing divider/pill treatment.
- [ ] 5.3 `ui/ui.js`: wire the control to re-open/re-fire the panel in
      place, keeping it open across the re-run.
- [ ] 5.4 `ui/ui.js`: send `forceRefresh: true` from the panel-level `⟳` and
      the per-provider `⟳`; do **not** send it on an ordinary panel open or
      on Enter in the shared query (design D5).
- [ ] 5.5 `routes/enrich.py`: `post_enrich` forwards `forceRefresh` to smia
      when the client supplies it, without originating it. smia accepts it
      on every kind (`routes/generic.py`'s `force_refresh_param` default;
      `routes/ipa.py` reads it explicitly).
- [ ] 5.6 Confirm the forwarded flag does not change the proxy's
      pass-through character — no retry, no fallback, no reinterpretation
      of smia's response.

## 6. Verification

- [ ] 6.1 Manually verify a word note with `text="legge til"` shows `legge`
      in the inflections query and `legge til` in the ipa/tts/translations
      queries.
- [ ] 6.2 Manually verify typing in `text` updates `lemma` live, and that
      editing `lemma` by hand stops it being overwritten.
- [ ] 6.3 Manually verify loading a different note re-enables lemma
      syncing.
- [ ] 6.4 Manually verify saving a new note and returning to the form
      leaves every field, query, and pending audio empty.
- [ ] 6.5 Manually verify opening panels on one note then navigating to
      another leaves every panel closed, and that reopening performs a
      fresh lookup rather than showing the first note's candidates.
- [ ] 6.6 Manually verify `⟳` re-queries every provider with the panel open
      throughout.
- [ ] 6.7 Manually verify `⟳` on an **unchanged** query actually re-consults
      the provider rather than returning the cached answer — the specific
      failure this change exists to prevent. Check smia's logs or a
      provider-side effect, not just the rendered value, since a correct
      re-run and a cache hit can look identical on screen.
- [ ] 6.8 Re-run the backend test suite; record the count and whether a
      real Postgres container was used. `routes/enrich.py` is touched, so
      this is not a pure-UI change.

**Note on verification**: no frontend test suite exists in this repo.
Record explicitly which of 6.1–6.7 were exercised against a running
backend and which were only reviewed in the diff.

## 7. Supersession record

- [ ] 7.1 Confirm the delta spec states the new query rule in full rather
      than patching `lemma-first-suggestions`' wording, so the archived
      change stays readable as what was believed at the time.
- [ ] 7.2 Confirm the removed "From text" requirement carries its reason
      and a migration note.
