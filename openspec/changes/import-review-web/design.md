## Context

`bulk-import-anki-csv` is functionally complete — 64 of its tasks are done,
the D13 attestation known-set is in, and `merge` has produced 9,009
candidates of which **7,022 are queued for review**. What remains is the
review itself, and the surface it ships with is `review.py`'s
`run_interactive`: a `for` loop over `print(format_candidate(row))` followed
by `input("[a]ccept / [r]eject / [e]dit then accept / [s]kip / [q]uit: ")`.

Measured against the real store (`import/candidates.db`):

```
review queue                               7,022
  with an audio_ref                        6,269
     core6k  hypertts-*  (machine TTS)     4,167   ← rejected by D10
     a1_31k              (human)           1,833
     ntnu                (human)             269
     none                                    753
  genuinely playable, human                2,102   (30%)

ordering signal
  ranked (freq / CEFR / chapter)           2,877   (41%)
  NO signal at all                         4,145   (59%)
     core6k 2,294 · a1_31k 1,684 · ntnu 167

text containing U+00A0                       140   (always article+word:
                                                    'å\xa0diskutere')
```

Environment facts that shape the options: Flask is already in
`requirements.txt`; `rich`/`textual` are not installed; `ffplay`, `paplay`
and `cvlc` exist on this machine; `ui/ui.css` (429 lines) is an existing
visual language for stabbur's own operator UI.

## Goals / Non-Goals

**Goals:**
- One decision per keypress, no `Enter`, no confirmation step.
- One candidate on screen at a time, visibly replaced by the next.
- Audio playback during review, human recordings only.
- Recoverable mis-presses.
- A review queue whose order actually reflects usefulness for most of its
  length.
- Nothing invisible or `repr()`-mangled reaching stabbur.

**Non-Goals:**
- No field editing (operator decision — see D4).
- No review of the auto-skipped set (operator decision); task 4.8's log
  dump is unchanged.
- No change to the judge, the known-set, or D13.
- No change to stabbur's own app, database, or UI.
- No new Python dependency.
- No remote access, no auth, no deployment. Localhost only.

## Decisions

### D1 — Web, not a TUI

Alternatives considered: raw-mode terminal via `termios`/`tty`; a
`textual`/`rich` TUI; keeping the line-based loop and only improving its
formatting.

Chosen: a localhost Flask app.

| | terminal | web |
|---|---|---|
| single keypress | raw `termios`, platform-specific, breaks piping and the existing `input_fn`/`print_fn` test seam | `keydown`, native |
| audio | spawn `ffplay` per clip; no scrub, no preload, process lifecycle to manage | `<audio>`: autoplay, replay, seek, preload-next |
| one-card swap | manual screen clear + ANSI cursor management | a CSS transition |
| new dependency | `textual`/`rich`, or hand-rolled | **none — Flask already required** |
| visual language | invent one | `ui/ui.css` exists to match |

Audio is the deciding factor: 6,269 of 7,022 candidates carry a clip, and
playback quality-of-life is the difference between judging a word in one
second and three. Everything else points the same way, and the zero-new-
dependency column settles it against `textual`.

**This does not reverse `bulk-import-anki-csv`'s D1** ("the candidate store
is local to the tool, not in stabbur's database; review happens here, not in
the stabbur UI"). A localhost Flask process reading `import/candidates.db`
*is* the import tool. It does not touch stabbur's Postgres, is not served by
`app.py`, adds nothing to `compose.yaml`, and is not reachable from
anywhere. Only the rendering medium changed; the architectural boundary is
exactly where D1 put it. This is called out explicitly because the change
superficially looks like a reversal and a future reader should not have to
re-derive that it isn't.

### D2 — The interface asks the question the operator is actually answering

The operator's own description of the task: *"the only thing i'll check is
whether i know it or not."* So the prompt is **"Do you already know this
word?"**:

```
   already know it   →  reject   (don't import)
   new to me         →  accept   (import as a draft)
```

The stored vocabulary stays `accept`/`reject` — `decision.decision`, the
tests, and `push` are unchanged. Only the operator-facing framing moves.

Rationale: "accept/reject" is the *pipeline's* word for the outcome, not the
operator's word for the judgement, and the mapping between them is inverted
in a way that is easy to get backwards at speed — "reject" feels like
rejecting the word, when it means rejecting the import. Over 7,022 decisions
a framing that requires a mental inversion each time will produce systematic
errors, not occasional ones. Labelling the actions by the judgement removes
the inversion from the operator's head.

### D3 — Audio is served from the archives by random access, human only

No extraction step and no blob staging. `zipfile` opens each `.apkg` once
and reads members on demand; a route resolves
`(source, audio_ref) → bytes`, and the page preloads the next candidate's
clip while the current one is on screen.

Only human sources are served: `ntnu` and `a1_31k`. A candidate whose only
audio is `core6k`'s `hypertts-*` or `freq6k`'s `ordpar-*` displays as having
no audio, because that is what will be true after `push`.

Autoplay note: browsers block autoplay until a user gesture has occurred.
The first keypress satisfies that for the rest of the session, so autoplay
is enabled from the second card onward and the first card requires one
explicit play. This is a browser constraint, not a design choice, and the UI
should not pretend otherwise.

### D4 — No editing; review is triage only

The terminal loop's `[e]dit then accept` path is removed, not ported.

Rationale (operator decision, and it holds up): every accepted candidate
enters stabbur as `status=draft` and will be edited there regardless, so
field editing during review is a second authoring surface competing with the
real one — and the worse of the two, since stabbur's editor has enrichment,
validation and suggestion panels that this tool will never have.

`decision.edited_fields_json` stays in the schema and is simply never
written. It is dead weight, but dropping it would mean a store migration for
no benefit, and — confirmed — **`push` never reads it**, so nothing
downstream is affected either way. Recorded here so a future reader does not
mistake the unused column for an unimplemented feature.

### D5 — Undo is multi-level and required

Single-keypress decisions with no confirmation make mis-presses certain
across 7,022 items, and a wrong keypress is invisible the moment the card
swaps. Undo steps backward through `decision` ordered by `decided_at`,
restoring the candidate to the queue; the last several decisions stay
visible on screen so an error made three cards ago can still be spotted.

Cheap by construction: `decision` is already an upsert keyed by signature,
so undo is a delete and a re-queue, with no extra bookkeeping.

Single-level undo was rejected: at speed the operator notices a mistake a
beat or two late, not immediately, which is exactly when one level is not
enough.

### D6 — `core6k`'s `cards.due` is a frequency rank and must be ingested

Measured: `cards.due` over `core6k` runs 1..6000 with 6,000 distinct values,
and note order confirms what it encodes —

```
å være · og · i · en · det · på · som · å ha · til · av · for · med · at ·
jeg · ikke · de · den · å bli · du · om
…tail: en handlepose · å vispe · å elte · å krydre · å gjespe · å sy
```

That is a frequency ordering, sitting unused in the archive. `ingest`
captures it; `normalize` carries it into `order_signal_json`; `merge`'s
ordering key consumes it alongside `freq6k`'s index.

Expected effect: ~2,294 of the 4,145 unranked candidates gain a rank,
raising ordering coverage from 41% to roughly 74%.

Two things it does not fix, stated so they are not mistaken for regressions:
the remaining ~1,851 (mostly `a1_31k`) still have no signal and still sort
last; and `core6k`'s rank and `freq6k`'s index are **different rankings of
different corpora** — they must be kept as separate, comparable-within-
source signals rather than merged into one pseudo-global rank, which would
be a fabricated number.

An alternative fallback — ranking by how many sources contributed a
candidate — was measured and rejected: 4,098 of the 4,145 unranked come from
exactly one source, so it does not discriminate at all.

### D7 — The human-audio rule moves from `push` to `merge`

D10 of `bulk-import-anki-csv` says human audio only, and task 7.1 applies it
at push. The consequence, measured: `merge`'s priority order
(`NTNU > A1 > core6k > freq6k > CSV`) selects `core6k`'s `hypertts-*` file
whenever neither human source has one, so 4,167 queue items carry an
`audio_ref` that will be thrown away later.

Filtering at merge instead makes `audio_ref` mean "the audio this note will
actually get", which is what both the review UI and any later inspection of
the candidate store need it to mean. Push's own filter stays as a
belt-and-braces check — it is cheap and it keeps D10 enforced at the
boundary that actually writes to stabbur.

### D8 — U+00A0 is normalised in `normalize`, not in the renderer

140 rows carry a non-breaking space between article and word
(`å\xa0diskutere`, `et\xa0eple`, `en\xa0etasje`).

Verified **not** to have corrupted anything upstream: Python's `\s` matches
U+00A0, so the article-stripping regex worked, `str.split()` splits on it,
and zero `head_lemma` values contain one. The signatures and verdicts are
correct.

It is still a data bug, because `text` is pushed to stabbur verbatim and
would carry the invisible character into notes and eventually onto cards,
where it also breaks exact-match search. Fixing it in the review renderer
would hide the symptom while still shipping the defect — so it is fixed at
`normalize`, mapping U+00A0 to a plain space along with any other
non-breaking/zero-width characters found. Measured: U+00A0 is currently the
only such codepoint in the corpus, but the normalisation should be written
as a class, not a single-character replacement, since nothing guarantees the
next source is as clean.

## Risks / Open Questions

- **The queue is ~7,000 decisions long.** Even at a good pace this is
  multiple sessions, so resumption is load-bearing; it already works
  (`pending_queue` derives position from `decision`) and must not regress.
- **Re-running `ingest`→`merge` to pick up D6/D7/D8 re-derives every
  candidate.** `decision` must survive untouched — the same guarantee the
  D13 switch depended on. Worth asserting as a test rather than trusting,
  since this is now the second time it has mattered.
- **Audio served from 450 MB of archives**: `zipfile` random access is fast,
  but handles must be opened once and reused rather than per request.
  Unmeasured; if it is slow, a one-time extraction of the 2,102 human clips
  is the fallback.
- **Open**: ~1,851 candidates (mostly `a1_31k`) still have no ordering
  signal after D6 and will sort last in arbitrary order. Acceptable for now;
  if that tail proves painful, `a1_31k`'s chapter tags
  (`A1_-_Beginner_Norwegian_with_Audio::05_Chapter_1_-_Vocabulary`) are an
  unexploited ordering signal.
