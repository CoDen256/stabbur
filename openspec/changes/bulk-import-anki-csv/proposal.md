## Why

stabbur has a working authoring loop but almost no content. Four Anki decks
and a textbook wordlist sitting in `import/` hold roughly 9,100 distinct
Norwegian lexemes with ~3,600 human audio recordings, 681 IPA
transcriptions, part-of-speech for 3,882 words, and a frequency ranking that
orders them by usefulness. Typing that in by hand is not realistic.

The complication is that the operator already knows the entire stock Mjølnir
deck — all 2,788 cards, including its sentences, rules and pronunciation
material — so importing everything blindly would bury genuinely new
vocabulary under thousands of words that are already learned. But filtering
naively is worse: measured against these sources, matching on tokens or
substrings would wrongly discard 560 idioms built entirely from known words
(`bli kvitt`, `bli klar over`, `bestemme seg`) and 181 particle verbs whose
head is known but whose meaning is not (`legge til` is not `legge`). Those
are precisely the hardest and most valuable items.

So the import needs a dedup model that compares whole lexemes rather than
word fragments, a merge across five sources that disagree about the same
word, and a review pass the operator can run, pause, resume and correct
without re-running anything.

## What Changes

- **A standalone import tool in this repo**, operating on the files already
  in `import/` — four `.apkg` archives and seven CSV chapter exports. Not a
  service, not part of the stabbur app, not deployed.
- **A local candidate store** (SQLite, in `import/`) holding every parsed,
  merged and judged candidate. Review happens here, *before* anything
  reaches stabbur.
- **Six resumable pipeline stages** — ingest, normalize, key, judge, merge,
  push — each idempotent and separately re-runnable, with a run log.
- **A known-set built from the stock bundle** (`mjolnir`'s module 2113),
  treating all of its Norwegian content as already known, but extracting it
  only from positions that are unambiguously Norwegian so that English
  explanation prose cannot masquerade as Norwegian vocabulary.
- **Lexeme-signature dedup**: `(head, particles, reflexive, complements)`.
  Auto-skip requires an exact signature match. Substring, prefix and
  head-only matching are prohibited outright.
- **One candidate per lexeme**, merged across sources by a fixed priority,
  with field-level conflicts recorded for review rather than silently
  resolved.
- **A review interface** over the candidate store, ordered by frequency rank
  then CEFR band then textbook chapter, so the operator works down a
  usefulness-ranked queue and can stop at any point.
- **Accepted candidates are pushed to stabbur** via its existing authoring
  API as `status=draft`, `origin=import`, with an `import_ref` — never as
  `ready`. stabbur's own draft→ready review remains the second, separate
  pass.
- **Human audio only.** NTNU and the A1 deck supply recordings; `core6k`
  (HyperTTS) and `freq6k` (`ordpar-*`, uniform 24 kHz/48 kbps) are
  machine-synthesised and are rejected entirely. Notes without audio are
  imported anyway and voiced later in stabbur.
- **Grammar is out of scope entirely.** `core6k`'s 225 `Grammar` notes have
  no audio, and sentence-length audio cannot practically be filled in later
  — unlike single words and phrases. No `type=grammar` notes and no
  `grammar_rule` rows are produced.

## Capabilities

### Added Capabilities
- `bulk-import`: ingesting external vocabulary sources, judging candidates
  against the operator's existing knowledge, merging across sources,
  operator review, and pushing accepted candidates into stabbur as drafts.

### Depends On
- `note-origin-provenance` — supplies the `origin=import` / `import_ref`
  fields this change stamps on every note it creates. That change must land
  first; it has no dependency in the other direction.

## Impact

- **New tool** (`scripts/import/` or similar): source parsers, the stock
  known-set extractor, the dedup/merge engine, the review interface, and the
  push client. No change to `app.py`, `routes/`, or `db/models.py`.
- **New local artifact**: a SQLite candidate store in `import/`, which is
  already gitignored along with the source archives.
- **stabbur app**: unchanged. The tool is an API client, using
  `POST /api/notes` and the blob upload endpoint exactly as the triage UI
  does. Nothing about this change requires the service to know imports
  exist beyond the provenance fields `note-origin-provenance` adds.
- **Audio**: ~3,600 human recordings uploaded as `blob/<sha256>`, which is
  the same content-addressed path captures already use, so duplicate
  recordings across sources collapse for free.
- **Expected volume**: ~9,100 candidates, ~1,500 auto-skipped, ~7,600
  presented for review across `type=word`, `expression` and `listening`.
  Roughly 35% will carry audio; the rest reach stabbur without it.
- **Out of scope**: `type=grammar` and `type=pronunciation` notes, re-import
  of the CSVs (one-shot by operator decision), `freq6k` Part 2, and any
  network enrichment — this change calls no provider, so there is no rate
  limiting to design.
