## 0. Prerequisite

- [ ] 0.1 `bulk-import-anki-csv` sections 1–5 are complete (they are — 64 tasks done, 9,009 candidates merged). This change re-runs `ingest`→`merge` and replaces `review`; it does not touch `key`/`judge` logic or D13.

## 1. Pipeline fixes the review depends on

- [ ] 1.1 `ingest.py`: capture `core6k`'s `cards.due` (1..6000, 6,000 distinct — verified a genuine frequency rank) onto its `raw_note` rows. Anki stores one row per card and `core6k` has 2 cards per note; take the note's minimum `due` and assert the two agree, rather than picking arbitrarily.
- [ ] 1.2 `normalize.py`: carry the core6k rank into `order_signal_json` as its **own** key, not merged with `freq6k`'s index — they rank different corpora (design D6).
- [ ] 1.3 `merge.py` / `order_sort_key`: consume the new signal. Assert ordering coverage rises from 2,877/7,022 (41%) to roughly 5,170 (74%); the remaining ~1,851, mostly `a1_31k`, still sort last.
- [ ] 1.4 `normalize.py`: normalise non-breaking and zero-width characters to a plain space. Write it as a **character class**, not a replacement of U+00A0 alone (design D8). Currently 140 rows are affected, all `article`+NBSP+`word`.
- [ ] 1.5 Assert the NBSP fix changes no signature and no verdict — it must not: `\s` already matched U+00A0, so article-stripping worked and zero `head_lemma` values carry one. A verdict diff here means something else moved.
- [ ] 1.6 `merge.py`: apply the human-audio-only rule when selecting `audio_ref` (design D7), so a candidate with only `hypertts-*`/`ordpar-*` audio records none. Expect `audio_ref` coverage to drop from 6,269 to ~2,102.
- [ ] 1.7 Leave `push.py`'s own human-audio filter (task 7.1) in place as a boundary check — D10 stays enforced where stabbur is actually written to.
- [ ] 1.8 Re-run `ingest`→`normalize`→`key`→`judge`→`merge`. **Assert `decision` is untouched** and the 2 existing decisions survive. This is the second time the D2/task 1.3 guarantee has carried a migration; make it a test, not an observation.

## 2. Review server

- [ ] 2.1 `scripts/import/web.py`: a Flask app bound to `127.0.0.1` only, reading `import/candidates.db`. Not served by `app.py`, nothing added to `compose.yaml`, no auth, no remote access (design D1).
- [ ] 2.2 `cli.py review` launches it and prints the URL. Remove `review.py`'s `run_interactive` and its `[e]dit` branch; **keep** `queue`, `pending_queue`, `progress`, `record_decision` unchanged and reuse them — the server is a new front end over the same functions, not a reimplementation.
- [ ] 2.3 Routes: current candidate, record decision, undo, audio. Keep them thin — all queue logic stays in `review.py`.
- [ ] 2.4 Audio route resolves `(source, audio_ref) → bytes` by `zipfile` random access into the `.apkg` archives. Open each archive **once** and reuse the handle (design D1's noted risk); serve `ntnu` and `a1_31k` only.
- [ ] 2.5 Return 404 for any audio request naming a synthesised source, so a UI bug cannot surface TTS that `merge` already excluded.

## 3. Review interface

- [ ] 3.1 Single candidate per screen, replaced on decision, with no accumulating scrollback. Show text, pos, translations, transcription, inflections, context, source attribution, conflicts, verdict + evidence, and audio state.
- [ ] 3.2 Match `ui/ui.css`'s existing visual language rather than inventing one — this is the same operator looking at the same kind of data.
- [ ] 3.3 Keyboard: one keypress per decision, no `Enter`, no confirmation. Actions labelled by the judgement, not the pipeline's vocabulary (design D2): "already know it" → `reject`, "new to me" → `accept`. Plus replay audio, undo, skip-for-now, and a help overlay.
- [ ] 3.4 **No field editing anywhere** (design D4). `decision.edited_fields_json` is never written; leave the column in place — `push` never reads it, so removing it would be a store migration for nothing.
- [ ] 3.5 Progress indicator: reviewed / remaining, from `progress()`.
- [ ] 3.6 Multi-level undo (design D5): step back through `decision` by `decided_at` desc, returning each candidate to the queue. Keep the last several decisions visible on screen so an error noticed three cards later is still correctable.
- [ ] 3.7 Audio: autoplay on card display, replay on keypress, and preload the next candidate's clip. Autoplay is blocked by the browser until a first user gesture — enable it from the second card on and require one explicit play for the first, rather than appearing broken (design D3).
- [ ] 3.8 Render text as text, never `repr()` — the `'å\xa0starte'` display was `format_candidate`'s `{value!r}`, and with 1.4 fixing the data this must not be reintroduced by the renderer.

## 4. Tests

- [ ] 4.1 `tests/test_import_ingest.py`: core6k `due` captured; the two cards per note agree.
- [ ] 4.2 `tests/test_import_normalize.py`: NBSP → space; a zero-width character is normalised by the same rule; signature/verdict unchanged (task 1.5).
- [ ] 4.3 `tests/test_import_merge.py`: a candidate whose only audio is `hypertts-*` records no `audio_ref`; one whose human source has audio keeps it; ordering coverage assertion from 1.3.
- [ ] 4.4 `tests/test_import_review.py`: replace the `run_interactive` and edit-path cases with route-level tests — decision recording, undo across several steps, resumption from `decision`, and that no route can write `edited_fields_json`.
- [ ] 4.5 Audio route: a human source streams; a synthesised source 404s; an unknown `audio_ref` 404s rather than erroring.
- [ ] 4.6 Full suite green against a real throwaway Postgres (repo convention) — though this change touches no stabbur table, `push`'s tests do.

## 5. Verification

- [ ] 5.1 Review 30–50 real candidates end to end: confirm one keypress per decision, that cards visibly swap, that audio plays and replays, and that undo recovers a deliberate mis-press three cards back.
- [ ] 5.2 Confirm the queue now opens on genuinely common words rather than arbitrary ones — the point of 1.1–1.3. If the first screenful still looks arbitrary, the ordering fix did not land regardless of what the coverage number says.
- [ ] 5.3 Confirm no candidate offers audio that `push` would later discard.
- [ ] 5.4 Stop and reopen review mid-queue; confirm it resumes at the first undecided candidate.
- [ ] 5.5 Record the real post-fix numbers (queue size, ordering coverage, human-audio coverage) in design.md, replacing the pre-run measurements — repo convention is to correct findings in place.
