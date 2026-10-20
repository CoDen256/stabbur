# stabbur

*Stabbur: the storehouse on stilts — where you keep what you gathered.*

The **learning content** service of the [Tun](../tun) ecosystem: captures come
in from the browser, get triaged and enriched, and become items you intend to
learn. Owns the canonical learning audio.

**Deliberately Mjølnir-independent** — no decks, no card ids, no occurrences,
no N/E/X/A. Those live in `mjolnir/hub`, which *pulls* from here. stabbur would
survive switching to a different SRS app entirely.

## Owns

```
capture      raw lexical intent grabbed in the wild, unclassified
item         triaged + enriched: text, translations, context, audio,
             pos, inflections, transcription, kind, status
grammar_rule shared explanations
blob/<sha256>  canonical learning audio (capture clips, TTS/Forvo results)
```

## Talks to

- **smia** — enrichment (`/inflect`, `/ipa`, `/tts`, `/translate`)
- **hover-translate** — posts captures here
- **mjolnir/hub** — pulls `GET /api/items?status=ready&since=…` plus blobs by hash.
  stabbur does not know hub exists.

## Status

Not implemented. Design: `../tun/docs/` (`03-data-model.md`, `02-services.md`).
