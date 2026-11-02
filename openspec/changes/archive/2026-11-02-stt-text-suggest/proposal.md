## Why

A note captured from audio-first sources can end up with `audio_blob` set
but `text` empty or rough — today the operator has to transcribe it by ear
and type it in by hand. smia already has a working, two-provider `/stt`
(`hf_whisper`, `elevenlabs`) that the smia UI itself already exercises via
file upload or in-browser recording, but nothing in stabbur calls it —
`routes/enrich.py`'s `ENRICHABLE_KINDS` explicitly excludes `stt` today with
the comment "no stt field exists on a note," which was true before this
change (the field it feeds is `text`, which does exist, it just wasn't
wired up).

## What Changes

- A new stabbur backend route, `POST /api/enrich/stt`, that takes a
  `provider` and (for an existing note) uses the note's own `audio_blob`
  bytes from stabbur's local blob storage, forwarding them to smia's
  `POST /stt` as multipart, and passing the response through.
- A "Propose from audio" button in the existing-note editor (`#/notes/:id`),
  shown only when the note has `audio_blob` set, opening an accordion with
  one row per configured `stt` provider (per smia's `stt-api` spec: a fixed,
  required-provider list — `hf_whisper` and `elevenlabs` today), each
  showing that provider's transcribed `text` with a "Use" button that writes
  it into the `text` field.
- Not added to the new-note form: a brand-new note has no `audio_blob` yet to
  transcribe from (the new-note audio-suggest change adds TTS there, the
  opposite direction) — this button only ever appears once a note has saved
  audio.
- `smia`: no changes — this consumes its existing, documented `/stt`
  contract exactly as the smia UI itself already does.

## Capabilities

### Modified Capabilities
- `smia-enrichment`: adds `stt` to the set of kinds the enrichment proxy
  supports, with its own route shape (multipart forward, not a JSON
  pass-through like the other four kinds) since `/stt`'s input is audio
  bytes rather than a JSON body, and its source is stabbur's own stored blob
  rather than operator-typed text.
- `note-editor`: adds a "Propose from audio" control to the existing-note
  editor, visible only when `audio_blob` is set, feeding the `text` field.

## Impact

- **stabbur backend**: new route `POST /api/enrich/stt` — reads the note's
  `audio_blob` bytes off local disk (`blob_storage.py`, which currently only
  exposes a file `path()`, not a bytes-read helper — one is needed), and
  forwards them as multipart to smia's `POST /stt` with the requested
  `provider` (and `lang`, from the note's `source_lang` mapped the same way
  the other enrich routes already do via `smiaLangCode`).
- **stabbur backend** (`smia_client.py`): needs a multipart-capable request
  helper alongside the existing JSON `post`/`get`/`get_bytes` — none of the
  current functions send `files=`.
- **stabbur UI** (`ui/index.html`, `ui/ui.js`): new "Propose from audio"
  button + suggest panel on the existing-note editor only, visible
  conditionally on `audio_blob` being set; a new candidate-rendering
  function for the `{provider, text}` shape (distinct from the
  `{candidates: [...]}` shape every other kind's panel renders).
- No schema changes — `text` is already a note field, written through the
  existing PATCH endpoint exactly like the IPA/translations "Use" buttons
  already do.
