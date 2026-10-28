## 1. Config & plumbing

- [x] 1.1 Add `SMIA_BASE_URL` and `SMIA_AUTH_TOKEN` to `.env.example` and
      `compose.yaml`'s backend service environment (compose.yaml done; .env.example
      edit blocked by this environment's sandbox permissions on dotenv files —
      operator needs to add the two lines by hand, see implementation summary)
- [x] 1.2 Add an `smia_client.py` (or similar) helper in stabbur that wraps
      `requests` calls to smia with the configured base URL + bearer token,
      used by every proxy route below — one place that knows how to talk to
      smia, not duplicated per route
- [x] 1.3 Confirm `stabbur-backend` and smia's backend share the
      `tun-shared` network in `compose.yaml` (already present for stabbur per
      D98; verify smia's compose does the same)

## 2. Backend: generic enrichment proxy

- [x] 2.1 Add `routes/enrich.py` with `POST /api/enrich/<kind>` for
      `kind` in `{ipa, translations, inflections, tts}`, building each kind's
      required body (`{text,lang}` / `{text,from,to}` / `{word,lang}` /
      `{text,lang}`) plus `provider`, forwarding to smia's `POST /<kind>`
- [x] 2.2 Add `GET /api/enrich/providers`, forwarding smia's `GET /providers`
- [x] 2.3 Pass smia's response status and body straight through on both
      success and failure — no retry, no fallback, no stabbur-side
      re-interpretation of smia's error shapes (per `smia-enrichment`
      capability's no-retry requirement)
- [x] 2.4 Reject an unconfigured `kind` (e.g. `stt`) with a clear 400 before
      ever calling smia
- [x] 2.5 Register the new blueprint in `app.py` alongside the existing
      `routes/blobs.py` / `routes/notes.py` registration

## 3. Backend: TTS "use" → real stabbur blob

- [x] 3.1 Check a live smia `/tts` response's candidate shape (resource id /
      sha256 field) against `tun/docs/06-smia.md`'s summary before writing
      this — resolve the design doc's open question here
- [x] 3.2 Add `POST /api/enrich/tts/use` taking the chosen candidate's
      identifying info, fetching the raw audio bytes from smia server-side
- [x] 3.3 Pipe those bytes through the existing blob-upload logic in
      `routes/blobs.py` (reuse, don't duplicate hashing/storage) and return
      the resulting stabbur `sha256`
- [x] 3.4 Test: using the same TTS candidate twice is harmless
      (content-addressed, idempotent)

## 4. Frontend: shared suggestion-panel plumbing

- [x] 4.1 Port the mockup's accordion mechanics (`assets/enrichment-mock.html`
      — `openPanel`/`closePanel`, per-provider row with editable query +
      retry, staggered reveal, reduced-motion handling) into `ui/ui.js` as
      real components wired to `API_BASE`/`authHeaders()` instead of mock
      fixtures
- [x] 4.2 Build a thin client for `/api/enrich/*` (mirrors `api()` in
      `ui/ui.js`) and a provider-catalog fetch used to render each panel's
      rows
- [x] 4.3 Confirm the panel components work unmodified from both
      `renderNewNote()` and `renderNoteDetail()` — no note id required

## 5. Frontend: per-field wiring

- [x] 5.1 Wire "Suggest pronunciations" next to transcription (IPA) — write
      a chosen candidate into `e_transcription` / `c_transcription`
- [x] 5.2 Wire "Suggest translations" with default `en`/`de` groups + "add a
      language" control — "Use" calls `addTranslationRow` with the group's
      language
- [x] 5.3 Wire "Suggest" next to the audio panel — "Use" calls the new
      `/api/enrich/tts/use` endpoint, then PATCHes the note's `audio_blob`
      exactly like the existing "Replace audio" flow does
- [x] 5.4 Wire the inflections lookup panel as read-only/copy-only — one
      panel, both configured providers' full paradigms, click-to-copy per
      form, no auto-fill into `e_inflections_fields` / `c_inflections_fields`
- [x] 5.5 Surface provider disagreement in the inflections panel (visual
      callout, as prototyped) rather than silently preferring one provider

## 6. Styling

- [x] 6.1 Port the mockup's visual language (palette tokens, type pairing,
      accordion/provider-row styling) into `ui/ui.css`, reusing stabbur's
      existing design tokens where they already overlap and extending where
      they don't — the mock is the reference for anything not already in
      `ui.css`

## 7. Tests

- [x] 7.1 Backend: proxy forwards the right body shape per kind (unit test
      per kind against a mocked smia)
- [x] 7.2 Backend: a smia failure/4xx/5xx passes through unchanged, with no
      retry attempted
- [x] 7.3 Backend: unconfigured/unknown `kind` and unknown `provider` return
      clear 400s without calling smia
- [x] 7.4 Backend: TTS "use" flow stores a real blob and returns a sha256
      usable by the existing `PATCH /api/notes/{id}` audio_blob field
- [x] 7.5 Manual: run through `assets/enrichment-mock.html`'s exact
      interaction set (suggest → retry with lemma → use; translations
      multi-language → use; inflections copy; audio suggest → use) against
      the real implementation and confirm the behavior matches

## 8. Docs

- [x] 8.1 Update `02-services.md`'s "stabbur ──enrich──► smia" note (or add a
      decision in `07-decisions.md`) once this ships, so the dependency
      arrow has real code behind it
