## 1. Storage

- [x] 1.1 `db/models.py`: add a single-row settings model — typed columns
      for the scalar preferences, one JSONB column for the per-kind
      provider preference (design D1). No cross-service references.
- [x] 1.2 `alembic/versions/`: migration creating the table. Do **not**
      seed a defaults row (design D2 — defaults belong in code so they can
      change without a data migration).
- [x] 1.3 Add a constraint or equivalent guard ensuring at most one
      settings row exists.

## 2. Defaults and reconciliation

- [x] 2.1 Define the code-level defaults for every preference in one
      place: provider ordering (empty — catalogue order), translation merge
      mode (append over `/`), per-provider override prefill (on), default
      target languages (`en`, `de`).
- [x] 2.2 Implement read-with-defaults so a missing or partial row returns
      a fully-populated settings object (design D2).
- [x] 2.3 Implement catalogue reconciliation (design D3): known providers
      in stored order first, unknown-but-stored skipped with position and
      enablement retained, catalogue-but-unstored appended enabled.
- [x] 2.4 Derive each kind's primary as the first enabled provider in the
      effective order — never store it separately.

## 3. API

- [x] 3.1 `routes/`: endpoint to read settings, returning the
      defaults-applied object.
- [x] 3.2 `routes/`: endpoint to write settings, accepting a partial
      update and rejecting unknown preference keys.
- [x] 3.3 Validate provider-ordering writes: names are strings, no
      duplicates within a kind, kinds are limited to those stabbur proxies.
      Do **not** reject a provider name absent from the current catalogue —
      D3 requires those to be retained, not refused.
- [x] 3.4 Register the routes behind the existing bearer-token hook in
      `auth.py` like every other authoring route.

## 4. Settings page

- [x] 4.1 `ui/index.html`: a settings page section and a rail entry under a
      config group.
- [x] 4.2 `ui/ui.js`: route handling for the settings page; load settings
      and the provider catalogue together.
- [x] 4.3 `ui/ui.js` / `ui/ui.css`: per-kind reorderable provider list with
      enable/disable, marking the current primary.
- [x] 4.4 `ui/ui.js`: mark providers that cannot answer automatically
      (manual-link providers such as `forvo`/`filmot`), so the operator can
      see why one is a poor primary.
- [x] 4.5 `ui/ui.js`: controls for translation merge mode, default target
      languages, and per-provider override prefill.
- [x] 4.6 Visual language follows `openspec/changes/origin-scoped-triage-belt/assets/triage-belt-mock.html`'s
      settings screen, which is the agreed mockup for this page.

## 5. Editor bindings

- [x] 5.1 `ui/ui.js`: translations "Use" consults merge mode — append to
      the language's existing row with ` / `, or add a separate row
      (design D6). Applies at point of use only; never rewrites stored
      translations.
- [x] 5.2 `ui/ui.js`: `buildEnrichProviderRow`'s override reveal prefills
      from the shared query by default, honouring the setting when it is
      turned off (design D5).
- [x] 5.3 `ui/ui.js`: confirm a collapsed override still falls back to the
      shared query, regardless of what it was prefilled with — the existing
      scenario must keep passing.
- [x] 5.4 `ui/ui.js`: translations panel builds its language groups from
      the configured default target languages rather than a hardcoded
      `SUGGEST_DEFAULT_LANGS`.

## 6. Verification

- [x] 6.1 Verify reading settings before any write returns a complete
      object with defaults, not an error or empty body.
- [x] 6.2 Verify a partial write leaves other preferences at their stored
      or default values.
- [x] 6.3 Verify reordering a kind changes its primary with no separate
      primary field to update.
- [x] 6.4 Verify disabling the first provider promotes the next enabled one
      to primary.
- [x] 6.5 Verify a stored provider missing from the catalogue is skipped
      without error, and that **reappearing restores its stored position
      and enabled state** — the reconciliation case most likely to be got
      subtly wrong (design D3 / Risks).
- [x] 6.6 Verify a catalogue provider absent from the stored order is
      appended enabled and does not become primary.
- [x] 6.7 Verify append merge mode produces one row reading `a / b`, and
      separate mode produces two rows.
- [x] 6.8 Verify changing merge mode does not alter any existing note.
- [x] 6.9 Verify the override reveal prefills by default and opens empty
      when configured to.
- [x] 6.10 Add backend tests for defaults-on-read, partial write, and the
      three reconciliation cases. This change has real backend logic, so
      unlike the UI-only changes it should not rely on manual verification
      alone.
- [x] 6.11 Re-run the full backend suite against a real Postgres container
      and record the count.

## 7. Spec tension record

- [x] 7.1 Confirm the `smia-enrichment` delta keeps the original
      prohibition verbatim for the proxy and adds the operator-ordered
      carve-out as a separate conditioned clause, rather than loosening the
      original sentence (design D4 / Risks).
- [x] 7.2 Confirm `routes/enrich.py` gains **no** chain or fallback logic —
      the walk lives in the browser as N ordinary pass-through lookups.
      Putting it on the server would rebuild the layer the original rule
      forbids, in the module that forbids it.
- [x] 7.3 Confirm the reversed override-prefill decision is recorded as
      superseding `lemma-first-suggestions`' empty-by-default reasoning,
      with the old behaviour still reachable.
