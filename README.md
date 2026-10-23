# stabbur

*Stabbur: the storehouse on stilts — where you keep what you gathered.*

The **learning content** service of the [Tun](../tun) ecosystem: captures come
in from the browser, get triaged and enriched, and become **notes** — authored,
reviewed content, language-agnostic. Owns the canonical learning audio.

**Deliberately Mjølnir-independent and language-agnostic** — no decks, no card
ids, no occurrences, no N/E/X/A, no idea what an SRS app is. Those live in
`mjolnir/hub`, which *pulls* from here. stabbur would survive switching to a
different SRS app, or adding a second source language, entirely.

The vocabulary split is deliberate: a **note** is authored content; a **card**
is what Mjølnir derives from a note. Same split Anki uses for the same reason.

## Owns

```
capture      raw lexical intent grabbed in the wild, unclassified
note         authored + reviewed: text, source_lang, translations (any
             languages), context, audio, pos, inflections, transcription,
             type (word/expression/listening/pronunciation/grammar),
             status (draft/ready — nothing more; stabbur never learns whether
             Mjølnir picked a note up, and doesn't need to)
grammar_rule shared explanations
blob/<sha256>  canonical learning audio (capture clips, TTS/Forvo results)
```

`audio_blob` is not required to reach `status=ready` — "ready" means
"reviewed and correct," not "has everything a consumer needs." Mjølnir's own
eligibility filter (audio required, no exceptions) is Mjølnir's concern.

## Talks to

- **smia** — enrichment (`/inflect`, `/ipa`, `/tts`, `/translate`)
- **hover-translate** — posts captures here
- **mjolnir/hub** — pulls `GET /api/notes?source_lang=no&status=ready&since=…`
  plus blobs by hash. stabbur does not know hub exists, and there is no
  callback — hub tracks what it has already minted entirely on its own side.

## Status

Not implemented. Design: `../tun/docs/` (`03-data-model.md`, `02-services.md`,
D74 for the note/card split rationale).
