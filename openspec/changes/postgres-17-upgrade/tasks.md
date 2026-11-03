## 0. Before you do anything

Read `design.md` in full, especially D-U1 (dump/restore, not `pg_upgrade`)
and D-U2 (a new volume name — v17 cannot read v16's on-disk format). This
touches live production data; every data-moving step below is marked
**(Operator)** deliberately — nothing here should be scripted and run
unattended on a first attempt.

## 1. Compose file change

- [x] 1.1 `stabbur/compose.yaml`: change `stabbur-postgres`'s `image:` from
      `postgres:16` to `postgres:17-alpine` (matching `mjolnir-postgres`'s
      exact tag, D-U3). Verified via `docker compose config --quiet`.
- [x] 1.2 Same file: change the volume reference from `stabbur-pg-data` to
      a new name (`stabbur-pg-data-17`), with an explicit `name:
      stabbur_stabbur-pg-data-17` override (same reasoning as the existing
      volumes' own `name:` overrides — identical volume whether brought up
      standalone or via `tun`'s `include:`). The old `stabbur-pg-data`/
      `stabbur_stabbur-pg-data` volume declaration is left in place,
      unused, so `docker volume ls` still shows it exists untouched.

## 2. Migration (Operator — live production data)

- [ ] 2.1 **(Operator)** Stop `stabbur-backend` (`docker compose stop
      stabbur-backend`) — no writes during the dump.
- [ ] 2.2 **(Operator)** Dump the current (v16) database:
      `docker exec stabbur-postgres pg_dump -U stabbur stabbur >
      stabbur-pre-upgrade.sql`. Keep this file until migration is fully
      verified.
- [ ] 2.3 **(Operator)** Record pre-migration row counts for comparison
      (e.g. `docker exec stabbur-postgres psql -U stabbur -d stabbur -c
      "SELECT 'notes', count(*) FROM notes UNION ALL SELECT
      'grammar_rules', count(*) FROM grammar_rules;"`).
- [ ] 2.4 **(Operator)** Apply the compose change (task 1) and bring up
      the new container: `docker compose up -d stabbur-postgres` — this
      creates the new, empty `stabbur-pg-data-17` volume and initializes a
      fresh `postgres:17-alpine` instance with the same
      `POSTGRES_USER`/`PASSWORD`/`DB` env as before.
- [ ] 2.5 **(Operator)** Restore: `docker exec -i stabbur-postgres psql -U
      stabbur -d stabbur < stabbur-pre-upgrade.sql`.
- [ ] 2.6 **(Operator)** Re-run the same row-count query from 2.3 against
      the new container — confirm it matches exactly.
- [ ] 2.7 **(Operator)** Restart `stabbur-backend` (`docker compose up -d
      stabbur-backend`) and confirm the app itself works normally (open
      its `/ui`, browse a few real notes).

## 3. Sign-off

- [ ] 3.1 **(Operator)** Keep the old `postgres:16` volume
      (`stabbur_stabbur-pg-data`) around, unused, for a self-chosen
      cool-down period before removing it (`docker volume rm
      stabbur_stabbur-pg-data`) — no fixed window decided in `design.md`,
      operator's own judgment.
- [ ] 3.2 If anything here contradicts or refines `design.md` during
      implementation, record it as an ADR amendment in
      `tun/docs/07-decisions.md`, per this project's established practice.
