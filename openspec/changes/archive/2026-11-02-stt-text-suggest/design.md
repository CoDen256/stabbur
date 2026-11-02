## Context

Every existing enrichment kind (`ipa`, `translations`, `inflections`, `tts`)
shares one shape: a JSON body goes to `routes/enrich.py`'s generic
`POST /api/enrich/<kind>` proxy, which forwards it to smia's matching
`POST /<kind>` and passes the JSON response straight back
(`smia_client.post`). `stt` breaks that shape in two ways:
- smia's `POST /stt` takes multipart audio bytes, not JSON (`stt-api` spec,
  `app.py`'s `/stt` route).
- The source of those bytes isn't something the operator types — it's the
  note's own already-stored `audio_blob`, read from stabbur's local blob
  storage (`blob_storage.py`).
- The response shape is `{provider, text}`, not `{provider, candidates: [...]}`
  — there's exactly one answer per provider, not a list to pick from.

## Goals / Non-Goals

**Goals:**
- Reuse the existing suggest-panel/accordion pattern (`openSuggestPanel`,
  `buildEnrichProviderRow`-style per-provider rows) as closely as the shape
  difference allows, rather than inventing a visually distinct component.
- Keep the "manual trigger only" rule (smia-enrichment-panel's existing
  decision) — STT is the most expensive/slowest kind by far (full model
  inference on an audio file), so this is non-negotiable here if anywhere.
- `stt` SHALL still require an explicit `provider` per smia's own `stt-api`
  spec (no single-provider auto-default) — the UI's provider rows satisfy
  this naturally since each row already names its provider.

**Non-Goals:**
- No change to smia.
- No STT suggestion on the new-note form (no `audio_blob` exists yet there —
  see proposal).
- No automatic overwrite-without-confirmation of non-empty `text` — addressed
  in D2 below.

## Decisions

### D1 — A dedicated `POST /api/enrich/stt` route, not folded into the generic proxy
`register_enrich_routes`'s generic `<kind>` route assumes a JSON body
forwarded as-is; `stt` needs to read a blob off disk and build a multipart
request instead. Rather than overloading the generic route with a
content-type branch, `stt` gets its own route function (same module,
`routes/enrich.py`), parallel to how `tts/use` already has its own bespoke
route for its different-from-the-norm behavior.
Request shape: `POST /api/enrich/stt` with JSON body `{provider, audio_blob}`
(the note's own `audio_blob` sha256, sent explicitly by the client rather
than the route re-reading the note from the DB — keeps the route stateless
and consistent with every other enrich route never touching stabbur's own
notes table).

### D2 — `smia_client.py` gains a multipart-forwarding helper
None of `post`/`get`/`get_bytes` send `files=`. Add
`post_multipart(path, files, data, timeout) -> (status, body)`, used only by
the new stt route. Rejected alternative: building the multipart request
inline in `routes/enrich.py` — keeping all smia-wire-format knowledge in
`smia_client.py` (its stated purpose) is consistent with every other route.

### D3 — `blob_storage.py` gains a `read(sha256) -> bytes` function
Today it only exposes `path()` (used by `routes/blobs.py`'s download route,
presumably via Flask's `send_file`). The new stt route needs raw bytes to
attach as the multipart payload, so a small `read()` is added alongside
`store`/`exists`/`path`.

### D4 — Candidate rendering: one text block per provider, not a use-per-candidate list
Since `/stt` returns exactly one `{provider, text}` per request (no
candidates array to choose among), the suggest panel's row renders the
transcribed text directly with a single "Use" button — structurally simpler
than `renderIpaCandidate`/`renderTtsCandidate`, which iterate over
`body.candidates`. A new `renderSttResult(prefix)` function (not reusing
`buildEnrichProviderRow`'s `candidates`-array assumption) handles this kind
specifically.

### D5 — Confirm before overwriting non-empty `text`
Every other "Use" button today overwrites its target field unconditionally
(transcription, audio) or additively (translations add a row, don't
overwrite). `text` is different: it's the note's primary content, already
filled in for most notes this button would ever be shown on (a note with
audio typically already has some text — the ask here is "clean it up /
confirm it," not "give me my first draft"). The "Use" button SHALL show a
confirmation (e.g. a native `confirm()`, matching the existing pattern
already used for grammar-rule delete) before overwriting a non-empty `text`
field; overwriting an empty one proceeds immediately.

## Risks / Trade-offs

- **[Risk]** STT inference (especially `hf_whisper`'s cold-start cloud call)
  can be slow — a suggest panel that fires on open (matching every other
  kind's `fire(defaultQuery)`-on-open behavior) could feel like it's hung.
  → **Mitigation**: same loading-skeleton pattern already used elsewhere
  (`suggest-skel`), no new mechanism needed, just confirm it reads
  reasonably during implementation; no auto-retry/polling added.
- **[Trade-off]** The route trusts the client-sent `audio_blob` sha256 rather
  than re-deriving it from the note id server-side. Accepted: every other
  enrich route already trusts client-sent field values the same way (e.g.
  `tts/use`'s `sha256`), and the blob is content-addressed/read-only from
  this route's perspective — a wrong or stale hash just 404s via
  `blob_storage.exists`, nothing unsafe happens.

## Migration Plan

- Additive only: one new backend route, one new `smia_client` helper, one new
  `blob_storage` function, one new UI panel. No schema changes, no existing
  route/field behavior changes.
