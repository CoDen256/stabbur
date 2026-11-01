## Context

`stabbur`'s note editor (`ui/index.html`, `ui/ui.js`) is a vanilla-JS,
no-build-step app with a hash router and one `<section class="page">` per
route; the same component code already serves both `#/new-note` and
`#/notes/:id`. `smia` (a separate repo/service/database) exposes
`POST /<kind>` for `ipa`/`translations`/`inflections`/`tts`/`stt`, each
content-addressed, cache-first, **one named provider per call, no fallback,
no fan-out** (D-S1 in `tun/docs/06-smia.md`), plus `GET /providers` for the
live catalog. Nothing in `stabbur` calls `smia` today — `02-services.md`'s
"stabbur ──enrich──► smia" arrow is currently just a line in a diagram.

A UI mockup was built and iterated on with the operator and is checked in at
`assets/enrichment-mock.html` in this change directory — **treat it as the
source of truth for layout, copy, interaction timing, and visual language**;
this design doc covers the parts the mockup can't show (the backend proxy,
real data shapes, error handling, the TTS byte-storage path).

## Goals / Non-Goals

**Goals:**
- One authenticated hop from browser → stabbur → smia, so the browser only
  ever holds stabbur's own bearer token.
- Reuse smia's existing per-kind contracts as-is (no new smia-side work).
- A TTS "Use" click results in real stabbur-owned audio (`blob/<sha256>`),
  never a reference into smia's private, non-canonical cache (D45).
- Per-provider editable query + retry, exactly as prototyped, so a provider
  with no entry for an inflected form can be retried against the lemma.
- Identical behavior on `#/new-note` (no note id yet) and `#/notes/:id`.

**Non-Goals:**
- No automatic mapping from a provider's inflection paradigm shape into
  stabbur's PoS-keyed inflection fields (`article`/`sg_indef`/`sg_def`/
  `pl_indef`/`pl_def`). The inflections panel is read-only/copy-only by
  explicit decision (proposal + mockup fix #1) — providers disagree with
  each other and with stabbur's own field shape often enough that silent
  auto-fill would hide real ambiguity.
- No auto-firing suggestions as the operator types (explicit decision —
  several providers are live scrapes or quota'd APIs; every lookup is
  operator-triggered).
- No new `stabbur` schema/columns. Suggestions are ephemeral client state;
  "Use" only ever writes to fields the note already has, through the
  existing note create/PATCH endpoints.
- No changes to `smia` itself.

## Decisions

### D1 — Backend-proxied (Option B), not direct browser→smia
The browser calls stabbur; stabbur calls smia server-side with its own
`SMIA_AUTH_TOKEN`. Rejected alternative: direct browser→smia with CORS
(Option A) — it would require a second bearer token box in the UI, expose
smia's address to the operator's browser (smia isn't reverse-proxied today
per the UI's own routing comment), and cannot satisfy the TTS→canonical-blob
requirement below without a server-side hop anyway. Since that hop is
mandatory for `tts`, doing it uniformly for all four kinds is simpler than
splitting transport strategy by kind.

### D2 — One generic proxy route, not one route per kind
`POST /api/enrich/<kind>` where `<kind>` is one of `ipa`, `translations`,
`inflections`, `tts`, forwarding the JSON body plus a `provider` field
straight to smia's `POST /<kind>`, and returning smia's response body and
status through unchanged (mirroring the shape of stabbur's own thin
pass-through style). `GET /api/enrich/providers` forwards smia's
`GET /providers`. Rejected alternative: four bespoke routes with per-kind
validation duplicated from smia — smia already validates its own inputs
(`_extract_ipa_input` etc. in `smia/app.py`); re-validating in stabbur would
just be a second place for the two services' contracts to drift apart. The
generic route still needs to know each kind's required body shape to build
the request to smia:
  - `inflections`: `{word, lang}`
  - `ipa`: `{text, lang}`
  - `translations`: `{text, from, to}`
  - `tts`: `{text, lang}`
  (`stt` is intentionally not proxied — out of scope, no stt field exists on
  a note today).

### D3 — No retry/fallback inside the proxy
A provider failure (smia's "no entry" shape, or a non-2xx) passes straight
back to the client. The client's per-provider retry button is what re-fires
with an edited query — this is a UI action, not server behavior, keeping the
proxy a thin, stateless pass-through consistent with smia's own D-S1 "no
chain, no fallback" rule.

### D4 — TTS "Use" fetches bytes server-side, then re-uploads through stabbur's existing blob path
Flow: client sends the chosen TTS candidate's resource id to a stabbur
endpoint (e.g. `POST /api/enrich/tts/use`) → stabbur calls smia to fetch the
raw audio bytes for that candidate (smia's `GET /tts/{key}` serves either
metadata or raw bytes depending on what's cached, per `smia/app.py`) →
stabbur pipes those bytes through its own existing `/blobs` upload handler,
which computes stabbur's own `sha256` and stores `blob/<sha256>` → the
resulting hash is returned to the client, which then does the normal
`PATCH /api/notes/{id}` (or holds it for the create-note flow) with
`audio_blob` set. No new blob-storage code path — this reuses the upload
handler `routes/blobs.py` already has; the only new code is "fetch from smia,
then call the existing upload internally instead of expecting multipart from
the browser."

### D5 — Suggestion state lives entirely in the client, never persisted mid-flight
Opening a panel, editing a provider's query, and "Use" are all pure
client-side state until a save (or the TTS re-upload call, which is
idempotent and content-addressed so firing it twice is harmless). This keeps
the new-note vs. existing-note code path identical — the enrichment panel
never needs to know whether the note has an id yet.

### D6 — Translations default to `en` + `de`, operator can add more
Matches the mockup exactly: two language groups shown by default (the
operator's actual working languages), with an "add a language" input that
spins up another group client-side. The proxy doesn't care about this
grouping at all — it's N independent `POST /api/enrich/translations` calls,
one per `(provider, target language)` pair, same as any other kind.

## Risks / Trade-offs

- **[Risk]** Live/scraped providers (dict.cc-style anti-bot, free-tier
  quotas) could be hit hard if "Suggest everything" is clicked repeatedly.
  → **Mitigation**: manual-trigger-only (no auto-fire) already bounds this to
  deliberate operator action; smia's own cache-first behavior absorbs repeat
  lookups of the same input.
- **[Risk]** stabbur's own computed `sha256` for a re-uploaded TTS candidate
  could differ from smia's if any transcoding happens in transit.
  → **Mitigation**: stream the exact bytes smia returns through stabbur's
  existing upload path unmodified; stabbur's hash is simply whatever that
  path already computes for any upload, so this introduces no new hashing
  logic to get wrong.
- **[Risk]** `stabbur`'s backend becomes a new availability dependency for
  `smia` reachability (previously independent, nothing in stabbur called
  out). → **Mitigation**: non-fatal, non-blocking — note create/save never
  depends on smia; a failed enrichment call only disables suggestions, never
  blocks saving a note (same spirit as D32's "hover still translates if the
  server is down" for the extension).
- **[Trade-off]** Not auto-mapping inflection paradigms into stabbur's
  fields is explicitly less automated than first imagined in the original
  ask. Accepted per operator's own fix #1 — ambiguity between providers (and
  between provider shape and stabbur's shape) makes a silent auto-fill risk
  writing a wrong form with no visible disagreement.

## Migration Plan

- Additive only — new routes, new UI panels, two new required env vars
  (`SMIA_BASE_URL`, `SMIA_AUTH_TOKEN`) for the stabbur backend. No existing
  endpoint, field, or UI behavior changes shape.
- Rollback is deleting the new routes/UI wiring; no data was ever written by
  this feature that isn't also writable by hand through the existing form.
- Requires `stabbur`'s backend container to be on the same network as
  `smia` (`tun-shared`, already defined in `stabbur/compose.yaml`) once both
  are deployed together; purely local dev can point `SMIA_BASE_URL` at a
  locally running smia instance.

## Open Questions

- Should the enrichment proxy cache anything on the stabbur side, or rely
  entirely on smia's own cache? Current lean: rely entirely on smia — it
  already does cache-first per `(kind, provider, sha256(input))`, and a
  second cache layer in stabbur would be one more place for the two to
  disagree.
- Exact resource-id shape for "use this TTS candidate" (does the client pass
  smia's candidate id, or do we need stabbur to re-run the same
  provider+input lookup to resolve bytes) — resolve during `tasks.md`
  implementation once smia's real `/tts` candidate shape is checked against
  a live response, not just the docs' summary table.
