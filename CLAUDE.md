# CLAUDE.md

## stabbur — part of the Tun ecosystem

The **learning content** service: captures → triage → enriched items, plus the
canonical learning audio blobs.

**Cross-repo design, decisions, pitfalls and the roadmap live in
`/home/coden/dev/tun/docs/` — start at `README.md`, then `07-decisions.md`.**
Do not re-derive settled decisions.

### Hard boundaries (D43, D44, D45)

- **No Mjølnir concepts here.** No decks, no 6-char card ids, no occurrences,
  no N/E/X/A, no card types a–e. All of that belongs to `mjolnir/hub`, which
  *pulls* from this service. stabbur must not know hub exists.
- **stabbur owns the canonical learning audio** as `blob/<sha256>`. smia is
  stateless and returns bytes; stabbur stores them.
- Separate database. **No cross-service foreign keys** — service independence
  has to be structural, not nominal.

### Depends on

`smia` for enrichment. Nothing else.

## Status

Not implemented. Relevant docs: `tun/docs/03-data-model.md` (note the ownership
banner at the top), `02-services.md`, `06-smia.md`.
