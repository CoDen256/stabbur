## 1. Storage

- [ ] 1.1 `db/models.py`: add a single-row settings model — typed columns
      for the scalar preferences, one JSONB column for the per-kind
      provider preference (design D1). No cross-service references.
- [ ] 1.2 `alembic/versions/`: migration creating the table. Do **not**
      seed a defaults row (design D2 — defaults belong in code so they can
      change without a data migration).
- [ ] 1.3 Add a constraint or equivalent guard ensuring at most one
      settings row exists.

## 2. Defaults and reconciliation

- [ ] 2.1 Define the code-level defaults for every preference in one
      place: provider ordering (empty — catalogue order), translation merge
      mode (append over `/`), per-provider override prefill (on), default
      target languages (`en`, `de`).
- [ ] 2.2 Implement read-with-defaults so a missing or partial row returns
      a fully-populated settings object (design D2).
- [ ] 2.3 Implement catalogue reconciliation (design D3): known providers
      in stored order first, unknown-but-stored skipped with position and
      enablement retained, catalogue-but-unstored appended enabled.
- [ ] 2.4 Derive each kind's primary as the first enabled provider in the
      effective order — never store it separately.

## 3. API

- [ ] 3.1 `routes/`: endpoint to read settings, returning the
      defaults-applied object.
- [ ] 3.2 `routes/`: endpoint to write settings, accepting a partial
      update and rejecting unknown preference keys.
- [ ] 3.3 Validate provider-ordering writes: names are strings, no
      duplicates within a kind, kinds are limited to those stabbur proxies.
      Do **not** reject a provider name absent from the current catalogue —
      D3 requires those to be retained, not refused.
- [ ] 3.4 Register the routes behind the existing bearer-token hook in
      `auth.py` like every other authoring route.

## 4. Settings page

- [ ] 4.1 `ui/index.html`: a settings page section and a rail entry under a
      config group.
- [ ] 4.2 `ui/ui.js`: route handling for the settings page; load settings
      and the provider catalogue together.
- [ ] 4.3 `ui/ui.js` / `ui/ui.css`: per-kind reorderable provider list with
      enable/disable, marking the current primary.
- [ ] 4.4 `ui/ui.js`: mark providers that cannot answer automatically
      (manual-link providers such as `forvo`/`filmot`), so the operator can
      see why one is a poor primary.
- [ ] 4.5 `ui/ui.js`: controls for translation merge mode, default target
      languages, and per-provider override prefill.
- [ ] 4.6 Visual language follows `openspec/changes/origin-scoped-triage-belt/assets/triage-belt-mock.html`'s
      settings screen, which is the agreed mockup for this page.

## 5. Editor bindings

- [ ] 5.1 `ui/ui.js`: translations "Use" consults merge mode — append to
      the language's existing row with ` / `, or add a separate row
      (design D6). Applies at point of use only; never rewrites stored
      translations.
- [ ] 5.2 `ui/ui.js`: `buildEnrichProviderRow`'s override reveal prefills
      from the shared query by default, honouring the setting when it is
      turned off (design D5).
- [ ] 5.3 `ui/ui.js`: confirm a collapsed override still falls back to the
      shared query, regardless of what it was prefilled with — the existing
      scenario must keep passing.
- [ ] 5.4 `ui/ui.js`: translations panel builds its language groups from
      the configured default target languages rather than a hardcoded
      `SUGGEST_DEFAULT_LANGS`.

## 6. Verification

- [ ] 6.1 Verify reading settings before any write returns a complete
      object with defaults, not an error or empty body.
- [ ] 6.2 Verify a partial write leaves other preferences at their stored
      or default values.
- [ ] 6.3 Verify reordering a kind changes its primary with no separate
      primary field to update.
- [ ] 6.4 Verify disabling the first provider promotes the next enabled one
      to primary.
- [ ] 6.5 Verify a stored provider missing from the catalogue is skipped
      without error, and that **reappearing restores its stored position
      and enabled state** — the reconciliation case most likely to be got
      subtly wrong (design D3 / Risks).
- [ ] 6.6 Verify a catalogue provider absent from the stored order is
      appended enabled and does not become primary.
- [ ] 6.7 Verify append merge mode produces one row reading `a / b`, and
      separate mode produces two rows.
- [ ] 6.8 Verify changing merge mode does not alter any existing note.
- [ ] 6.9 Verify the override reveal prefills by default and opens empty
      when configured to.
- [ ] 6.10 Add backend tests for defaults-on-read, partial write, and the
      three reconciliation cases. This change has real backend logic, so
      unlike the UI-only changes it should not rely on manual verification
      alone.
- [ ] 6.11 Re-run the full backend suite against a real Postgres container
      and record the count.

## 7. Spec tension record

- [ ] 7.1 Confirm the `smia-enrichment` delta keeps the original
      prohibition verbatim for the proxy and adds the operator-ordered
      carve-out as a separate conditioned clause, rather than loosening the
      original sentence (design D4 / Risks).
- [ ] 7.2 Confirm `routes/enrich.py` gains **no** chain or fallback logic —
      the walk lives in the browser as N ordinary pass-through lookups.
      Putting it on the server would rebuild the layer the original rule
      forbids, in the module that forbids it.
- [ ] 7.3 Confirm the reversed override-prefill decision is recorded as
      superseding `lemma-first-suggestions`' empty-by-default reasoning,
      with the old behaviour still reachable.
