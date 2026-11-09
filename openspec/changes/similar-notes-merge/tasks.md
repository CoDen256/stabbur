## 1. Verify the assumption first

- [x] 1.1 Confirm `pg_trgm` is available in the running `postgres:17-alpine` container (`SELECT * FROM pg_available_extensions WHERE name='pg_trgm'`). **Do this before anything else** — every fallback design is substantially heavier, and design D2 is written assuming it is present (one query, not a guess).

## 2. Schema and index

- [x] 2.1 Alembic migration: `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
- [x] 2.2 GIN trigram index on the expression used for comparison — the article/infinitive-stripped, lowercased form of `notes.text`, not the raw column, so `å oppleve` and `oppleve` compare as the same string.
- [x] 2.3 No new columns. Confirm explicitly that no `merged_from` field is added (design D6, operator decision).
- [x] 2.4 Downgrade drops the index; leave the extension in place (dropping a shared extension on downgrade is more dangerous than leaving it).

## 3. Similarity queries

- [x] 3.1 Spelling signal: `pg_trgm` similarity over the stripped/lowercased text, threshold **0.4** (design D1, measured). Make the threshold configurable rather than compiled in — design's stated risk is that it needs revisiting under real usage.
- [x] 3.2 Exclude `type=listening` from the spelling signal entirely (design's non-goal; sentence similarity is noise).
- [x] 3.3 Morphology signal: notes whose `inflections` share a surface value. **Exclude the `article` key** — it holds `en`/`et`/`ei` and would otherwise relate thousands of nouns to each other (design D1, and a spec requirement in its own right).
- [x] 3.4 Semantic signal: notes sharing a normalised translation (lowercase, strip a leading `a`/`an`/`the`/`to`).
- [x] 3.5 A note matched by several signals appears once, carrying every reason. Do not emit duplicate rows per signal.
- [x] 3.6 Exclude the note itself, and exclude notes with a different `source_lang` (non-goal, but cheap to get right now).

## 4. API

- [x] 4.1 Similar-notes lookup for a given note id, returning each match with its reasons, status, origin, and which fields it actually has (audio / transcription / inflections / context) — the panel needs that to show what is worth taking.
- [x] 4.2 Merge endpoint: a surviving note id, one or more absorbed note ids, and the per-field selections to apply.
- [x] 4.3 **Enforce the status rules server-side** (design D3): absorbed notes must all be `draft`; reject otherwise with a clear error. The UI must not be the only thing preventing a forbidden merge.
- [x] 4.4 Absorbed rows are hard-deleted. Assert `deleted_at` is never written by this path.
- [x] 4.5 The surviving note's `updated_at` is bumped (D82 — builder's `since` pull must see it).
- [x] 4.6 `origin` is untouched by a merge — it is immutable (`note-origin-provenance` D5), so the survivor keeps its own.
- [x] 4.7 Merge is transactional: field copies and deletions commit together or not at all.

## 5. UI

- [x] 5.1 Similar-notes panel in the note editor, matching `ui/ui.css`'s existing visual language.
- [x] 5.2 Same panel in the triage belt (`origin-scoped-triage-belt`'s `note-triage` surface) — coordinate rather than duplicate the markup.
- [x] 5.3 Each match shows its reason label(s): *spelled alike* / *same word family* / *related*. Never a bare score in place of the reason (design D1).
- [x] 5.4 Each match shows status, origin, and what it has to offer (audio, IPA, inflections, context).
- [x] 5.5 Per-field "take" actions, with audio the most prominent — it is the motivating case.
- [x] 5.6 Translation-matched notes in a **collapsed-by-default** section labelled as related, not duplicate (design D5).
- [x] 5.7 Multi-select for many-to-one merge, with the absorbed notes named explicitly before the operator commits.
- [x] 5.8 A merge that the rules forbid is not offered — and when attempted anyway, the server's rejection is surfaced legibly.
- [x] 5.9 "Nothing related" is shown plainly rather than as an empty control.

## 6. Tests

- [x] 6.1 Each signal in isolation: `oppleve`/`opplevelse` by spelling (0.583, above threshold); `blogg`/`blogger`/`blogge` by shared inflected form; two "connection" synonyms by translation.
- [x] 6.2 Two `en`-gender nouns sharing nothing else are **not** related (task 3.3's article exclusion).
- [x] 6.3 A `listening` note reports no spelling similarity.
- [x] 6.4 A note matched by two signals appears once with both reasons.
- [x] 6.5 Status rules: ready←draft permitted; draft←draft permitted; draft←ready rejected; ready←ready rejected. Each asserted at the API, not only in the UI.
- [x] 6.6 After a permitted merge: absorbed row gone, `deleted_at` null everywhere, survivor's `updated_at` bumped, survivor's `origin` unchanged.
- [x] 6.7 Taking audio copies the `sha256` reference and stores no second blob.
- [x] 6.8 A failed merge rolls back entirely — no partial field copy, no orphaned deletion.
- [x] 6.9 Full suite against a real throwaway Postgres (repo convention) — mandatory here, since `pg_trgm` and the GIN index cannot be exercised on SQLite.

## 7. Verification

- [ ] 7.1 Re-measure the threshold distribution against the real `notes` table once imported drafts are present; design's 0.4 figures come from the import candidate store. Adjust if the shape differs materially.
- [ ] 7.2 Open 20 real notes and judge whether the panel feels intelligent — specifically whether the reason labels make the noise (`tur`/`turbo`) read as obviously-ignorable rather than as the tool being wrong.
- [ ] 7.3 Merge a real near-duplicate family end to end, taking audio from one and transcription from another.
- [ ] 7.4 Record the measured-on-real-data numbers in design.md, replacing the candidate-store measurements (repo convention: correct findings in place).
