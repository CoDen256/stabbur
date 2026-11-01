## Why

Filling in a note's transcription, translations, inflections, and audio is
entirely manual today — the operator types or pastes everything by hand into
`stabbur`'s note editor. `smia` already exists and knows how to look this up
(`ipa`, `translations`, `inflections`, `tts`, each with multiple providers),
but nothing in `stabbur` calls it yet (`02-services.md`'s dependency arrow
"stabbur ──enrich──► smia" has no code behind it). This change wires the two
together: a per-field "Suggest" control in the note editor that fans out to
every configured provider for that field, shows the candidates side by side,
and lets the operator copy the one they want into the note with one click —
without losing the ability to override a provider's input (e.g. querying the
lemma instead of the inflected surface form when a provider has no entry for
it).

## What Changes

- New stabbur backend endpoints that proxy enrichment lookups to `smia`
  (Option B from the design discussion: the browser never talks to `smia`
  directly — `stabbur` holds the one `SMIA_AUTH_TOKEN`, `smia`'s address
  stays internal, and TTS responses are pulled into `stabbur`'s own
  `blob/<sha256>` store per D45, since `smia`'s audio cache is explicitly
  non-canonical).
- A per-field "Suggest" accordion in the note editor for **transcription**
  (IPA), **translations**, and **audio** (TTS) — opens beneath the field it
  feeds, fires on click only (never on typing), shows one row per configured
  provider with an editable query input + retry, and a "Use" button that
  writes the chosen candidate straight into the note form.
- Translations suggest per target language, defaulting to `en` and `de`, with
  an "add a language" control for anything else.
- An **inflections lookup panel** that is read-only by design: each
  provider's full paradigm shown as its own table (providers disagree on
  spelling/forms often enough — e.g. ordbank vs. kaikki on a plural definite
  — that auto-filling one answer would silently hide the disagreement), with
  click-to-copy per form so the operator can paste whichever cell matches
  into stabbur's own PoS-shaped inflection fields.
- Works identically for a brand-new, not-yet-saved note and for an existing
  one being edited — suggestions only ever need the in-progress form values,
  never a saved note id.
- A gold-standard UI reference mock is checked in at `assets/enrichment-mock.html`
  (open it in a browser) — the implementation should match its interaction
  model, visual language, and copy exactly unless a technical constraint
  forces a deviation (call that out explicitly in review if it comes up).

## Capabilities

### New Capabilities
- `smia-enrichment`: stabbur-side backend capability that proxies `ipa`,
  `translations`, `inflections`, and `tts` lookups to `smia` on the
  operator's behalf — one authenticated hop, provider catalog pass-through,
  and (for `tts` only) pulling the resulting audio bytes into stabbur's own
  blob store so a "Use" click on a TTS candidate produces a real
  `audio_blob` reference, not a link into smia's private cache.

### Modified Capabilities
- `note-editor`: adds the per-field Suggest accordions (transcription,
  translations, audio) and the read-only inflections lookup panel described
  above to both the new-note and note-detail forms. No existing note-editor
  requirement is removed or weakened — this is additive.

## Impact

- **stabbur backend**: new routes (e.g. `POST /api/enrich/<kind>`) that
  forward to `smia`'s `POST /<kind>` endpoints using a server-held
  `SMIA_BASE_URL`/`SMIA_AUTH_TOKEN`; a new code path that, on a TTS "Use",
  fetches the chosen candidate's audio bytes from `smia` and re-uploads them
  through stabbur's existing `/blobs` upload rather than storing a reference.
- **stabbur UI** (`ui/index.html`, `ui/ui.js`): new accordion components
  wired to the fields listed above, on both `#/new-note` and
  `#/notes/:id`; no changes to existing fields' validation or save behavior.
- **Config**: `SMIA_BASE_URL` and `SMIA_AUTH_TOKEN` become required stabbur
  backend environment variables (see `.env.example`); `compose.yaml` needs
  stabbur's backend to reach `smia` on the `tun-shared` network.
- **No stabbur schema changes** — suggestions are ephemeral UI state; only
  the fields a note already has (`transcription`, `translations`,
  `inflections`, `audio_blob`) are ever written, through the existing
  PATCH/POST note endpoints.
- **smia**: no changes — this change is purely a consumer of its existing,
  documented contract (`tun/docs/06-smia.md`).
