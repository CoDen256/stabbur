# CLAUDE.md

## stabbur — part of the Tun ecosystem

The **learning content** service: captures → triage → reviewed **notes**, plus
the canonical learning audio blobs. A note is authored content; "card" is a
different word for a different entity Mjølnir derives — never use them
interchangeably in this repo.

**Cross-repo design, decisions, pitfalls and the roadmap live in
`/home/coden/dev/tun/docs/` — start at `README.md`, then `07-decisions.md`.**
Do not re-derive settled decisions.

### Hard boundaries (D43, D44, D45, D74)

- **No Mjølnir concepts here.** No decks, no 6-char card ids, no occurrences,
  no N/E/X/A, no card types. All of that belongs to `mjolnir/hub`, which
  *pulls* from this service. stabbur must not know hub exists.
- **Language-agnostic.** `source_lang` is a real column; `translations` is
  `[{lang, text}]` for any languages, not fixed en/de. `inflections` is a flat
  JSONB, Norwegian-shaped, until a second `source_lang` actually exists.
- **`status` is `draft`/`ready` only.** Never add a "published" state here —
  stabbur never learns whether Mjølnir picked a note up, by design (D74). That
  tracking is entirely `mjolnir/hub`'s own ledger, never pushed back.
- **`audio_blob` is not required for `status=ready`.** "Ready" means reviewed
  and correct, nothing about what a consumer needs. Mjølnir's own eligibility
  filter (audio mandatory, no type-based exception) lives on Mjølnir's side.
- **stabbur owns the canonical learning audio** as `blob/<sha256>`. smia is
  stateless and returns bytes; stabbur stores them.
- Separate database. **No cross-service foreign keys** — service independence
  has to be structural, not nominal.

### Depends on

`smia` for enrichment. Nothing else.

## Status

Not implemented. Relevant docs: `tun/docs/03-data-model.md`, `02-services.md`,
`06-smia.md`, and **D74** for why `item` became `note`.
