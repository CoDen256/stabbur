## Why

stabbur has a working authoring loop but almost no content. Four Anki decks
and a textbook wordlist sitting in `import/` hold roughly 9,100 distinct
Norwegian lexemes with ~3,600 human audio recordings, 681 IPA
transcriptions, part-of-speech for 3,881 words, and a frequency ranking that
orders them by usefulness. Typing that in by hand is not realistic.

The complication is that the operator already knows the entire stock Mjølnir
deck — all 2,790 cards, including its sentences, rules and pronunciation
material — so importing everything blindly would bury genuinely new
vocabulary under thousands of words that are already learned. But filtering
naively is worse: matching on substrings or on a candidate's head alone
would wrongly discard particle verbs whose head is known but whose meaning
is not — `legge an` is not `legge` — and those are the hardest and most
valuable items in the set.

The knowledge model, stated by the operator: **every Norwegian word in the
stock cards is known, together with every word combination actually attested
there, and nothing that is not.** So `legge til` is known (stock has `legge
til noen i kopi`), `vi`/`bor`/`der`/`vi bor der` are all known (stock has
the sentence), and `legge an` is not known at all.

So the import needs a known-set that is exact attestation rather than
fragment matching, a merge across five sources that disagree about the same
word, and a review pass the operator can run, pause, resume and correct
without re-running anything.

**Amended after section-4 review (design D13).** An earlier version of this
proposal built the known-set by extracting lexemes from stock's card
structure, and cited `bli kvitt` as an idiom that must survive filtering.
Both were wrong: stock attests `bli kvitt` (`"Bli kvitt depresjonen ved
hjelp av en psykolog"`), so it is known; and structure-based extraction
produced seven successive bugs, every one found by operator inspection
rather than by a test, because "is the extracted lexeme set correct?" has no
ground truth to test against. D13 replaces it.

## What Changes

- **A standalone import tool in this repo**, operating on the files already
  in `import/` — four `.apkg` archives and seven CSV chapter exports. Not a
  service, not part of the stabbur app, not deployed.
- **A local candidate store** (SQLite, in `import/`) holding every parsed,
  merged and judged candidate. Review happens here, *before* anything
  reaches stabbur.
- **Six resumable pipeline stages** — ingest, normalize, key, judge, merge,
  push — each idempotent and separately re-runnable, with a run log.
- **A known-set built from the stock bundle** (`mjolnir`'s module 2113) as
  every token and every attested word sequence of its Norwegian text, closed
  expansively over inflection, with no upper length limit. Norwegian text is
  identified by scoring each line against a lexicon built from the import
  sources themselves — **not** from stock's deck, field or card structure,
  which is what makes the extraction testable (design D13).
- **Attestation-based skipping.** A candidate skips only if its own full
  surface sequence is attested. Substring, prefix, head-only and
  token-subset matching are prohibited outright. Lexeme signatures
  `(head, particles, reflexive, complements)` are retained for merging
  candidates, not for deciding skips.
- **A deny-list that vetoes weak evidence only**, never direct attestation —
  it may not block a word stock teaches as its own subject.
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
- **Expected volume**: 9,009 distinct candidate signatures, ~1,683
  auto-skipped under D13, ~7,326 presented for review across `type=word`,
  `expression` and `listening`. Roughly 35% will carry audio; the rest reach
  stabbur without it.
- **Out of scope**: `type=grammar` and `type=pronunciation` notes, re-import
  of the CSVs (one-shot by operator decision), `freq6k` Part 2, and any
  network enrichment — this change calls no provider, so there is no rate
  limiting to design.
