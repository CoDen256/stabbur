## Why

Several separate requests turn out to need the same missing thing: somewhere
to put an operator preference.

- Choosing a provider for every field, every time, is the bulk of the
  tedium in authoring a note. The operator knows which provider they trust
  for each kind; the editor makes them re-express that on every note.
- Using a second translation suggestion for a language the note already has
  adds a second row, when the wanted behaviour is usually to extend the
  existing one (`to add / to append`). Which of the two is right is a
  preference, not a fact.
- A per-provider query override opens empty, by an explicit earlier
  decision — "so it reads unambiguously as a different input rather than a
  copy". In use that reads as an obstacle: the common case is tweaking the
  shared query, not writing an unrelated one.

stabbur has no settings storage at all today — no table, no endpoint, no
page. So the first three items are blocked on the fourth, and this change
delivers the storage, the page, and the three preferences that motivated
them.

Settings live in **stabbur's own database**, not in browser storage. They
are operator-level configuration that should survive a browser change and
be inspectable the same way every other stabbur record is.

## What Changes

- **A settings capability**: a single stored settings record, read and
  written over the authoring API, with defaults applied for anything unset
  so the service is fully functional before the page is ever opened.
- **A settings page** in the existing left rail, grouped by what the
  setting affects rather than by where it is implemented.
- **Per-kind provider preference**: for each enrichment kind, an operator
  ordering of that kind's providers plus which are enabled. The first
  enabled provider is that kind's primary. Providers themselves still come
  from the enrichment service's catalogue — stabbur stores only the
  ordering and the enabled flags, and tolerates the catalogue changing
  underneath it.
- **Translation merge mode**: using a second suggestion for a language the
  note already has either appends to the existing row separated by `/`
  (new default) or adds a separate row (today's behaviour).
- **Per-provider query override starts prefilled** with the panel's shared
  query, reversing the earlier empty-by-default decision. Configurable, so
  the earlier behaviour remains available.
- **An explicit carve-out in the enrichment pass-through rule.**
  `smia-enrichment` currently states the system "SHALL NOT automatically
  retry the same kind against a different provider". An operator-configured
  fallback order is a retry against a different provider, so the rule is
  modified rather than quietly broken — narrowed to what it was actually
  protecting (the proxy never second-guesses a provider's answer) while
  permitting an operator-initiated, operator-ordered, visible walk down
  their own list.

## Capabilities

### Added Capabilities

- `operator-settings`: storage, defaults, and the editing surface for
  operator-level preferences. New capability — nothing in stabbur stores a
  preference today.

### Modified Capabilities

- `smia-enrichment`: the no-fallback rule is narrowed to the proxy, so an
  operator-driven provider order can exist above it without contradicting
  the spec.
- `note-editor`: translation merge behaviour and per-provider override
  prefill become settings-driven rather than fixed.

## Impact

- **stabbur schema**: a new single-row settings table, with an Alembic
  migration. No cross-service references; nothing Mjølnir-shaped.
- **stabbur backend** (`routes/`): a settings read/write endpoint, and
  defaults applied on read so an empty table behaves like a configured one.
- **stabbur UI** (`ui/index.html`, `ui/ui.js`, `ui/ui.css`): a new settings
  route and page; provider ordering control; the editor reads merge mode
  and override-prefill from settings.
- **Sequencing**: depends on nothing, but `origin-scoped-triage-belt` and
  `examples-context-suggestions` both consume it. Land it before them.
- Independent of `bulk-import-anki-csv` (concurrent, confined to `import/`
  and `scripts/import`).
