> **Status at archive time: Forvo capture shipped and confirmed working.
> filmot/YouTube capture is implemented but BLOCKED — still failing against
> real YouTube after four rounds of live-debugged fixes, postponed by
> operator decision. See `tasks.md` task 6.3 for the full history before
> picking this back up.**

## Why

smia's `forvo` and `filmot` `/tts` providers never had (and will never have) a
free API — they always "succeed" with `{candidates: [], url}`: a link to
that provider's own site, pre-filled, for a human to check by hand
(`smia/adapters/manual_link.py`). Today stabbur's suggest panel treats
`candidates.length === 0` as a hard failure for every TTS provider alike
(`buildEnrichProviderRow`'s `fire()`) and shows "No entry found" — the `url`
smia already computed and returned is silently discarded. The operator gets
no way to actually use these two providers at all, even though checking a
Forvo or filmot page by hand and bringing back real audio was the entire
point of their existing in minimal form.

## What Changes

- The TTS suggest panel surfaces `url` when a provider returns
  `{candidates: [], url}` instead of showing "No entry found": an
  "Open forvo.com ↗" / "Open filmot.com ↗" link the operator can click to
  check the site by hand, plus an input for pasting back what they found.
- **Forvo path**: the operator opens the link, picks a pronunciation on
  forvo's site, and pastes back a direct audio file link. Stabbur downloads
  that URL server-side, stores the bytes as a normal content-addressed blob,
  and hands it to the note's existing audio panel — including the waveform
  trim UI that already exists for any attached audio (`audio_sel_ms`), since
  a Forvo clip may need trimming same as anything else.
- **filmot path**: the operator opens the link, finds a YouTube video and
  timecode on filmot's results, and pastes back that YouTube URL (with its
  timecode). Stabbur downloads just that video's audio for a window around
  the timecode (±2 seconds) — not the whole video — using `yt-dlp` +
  `ffmpeg` server-side, stores the resulting clip as a blob, and hands it to
  the same existing trim UI for the operator to narrow down further by hand.
- Both paths reuse the existing attach mechanism exactly
  (`audio_blob` + `audio_sel_ms: null` PATCH, same as "Replace audio" and the
  TTS "Use" button already do) — no new attach code path, only new ways to
  arrive at a blob.
- Arbitrary operator-pasted URLs are accepted for both paths (confirmed with
  operator) — this is a single-operator internal tool, not a public-facing
  service.
- `smia`: no changes — it already returns the `url` this change starts
  using; the download/trim pipeline is entirely new stabbur-side
  infrastructure.

## Capabilities

### New Capabilities
- `manual-link-audio-capture`: stabbur backend capability for turning an
  operator-supplied link (a direct audio file URL, or a YouTube URL +
  timecode) into a stabbur-owned, content-addressed audio blob — downloading
  a direct file as-is for the Forvo path, and downloading + extracting a
  ±2-second audio window via `yt-dlp`/`ffmpeg` for the filmot/YouTube path.

### Modified Capabilities
- `note-editor`: the TTS suggestion panel surfaces a manual-link provider's
  `url` and accepts a pasted-back link instead of showing a bare "no entry"
  failure for `forvo`/`filmot`.

## Impact

- **stabbur backend**: new routes to accept a pasted link and resolve it to a
  stored blob — one for a direct audio URL (Forvo), one for a YouTube
  URL+timecode (filmot), both ending in the same "blob exists, ready to
  attach" response shape the UI already knows how to consume.
- **New runtime dependencies**: `yt-dlp` (Python package) and `ffmpeg`
  (system binary) — neither is in `requirements.txt`/`Dockerfile` today.
- **stabbur UI** (`ui/ui.js`, `ui/index.html`): TTS suggest-panel rendering
  branches on `{candidates: [], url}` vs. a real candidate list; new
  paste-a-link inputs and wiring into the existing attach-then-trim flow.
- **No smia changes.**
- **No schema changes** — same `audio_blob`/`audio_sel_ms` fields as every
  other audio-attach path.
