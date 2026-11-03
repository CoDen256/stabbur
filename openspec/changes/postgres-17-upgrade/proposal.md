## Why

`stabbur-postgres` runs `postgres:16`; `mjolnir-postgres` runs
`postgres:17-alpine`. The planned unified backup service (`tun`'s
`compose-backup-service`) needs a `pg_dump` matching each server's major
version — with two different majors in the stack, that means installing
and correctly invoking two separate versioned client binaries in one image
(confirmed workable via Debian's PGDG apt repo, but still a real,
avoidable bit of complexity). Unifying both to the same major version
removes it entirely: one client package, one `pg_dump` invocation path,
nothing to get wrong. 16→17 is a well-trodden, low-risk upgrade with no
breaking changes relevant to a plain SQLAlchemy/Flask app.

## What Changes

- **`stabbur-postgres`'s image moves from `postgres:16` to
  `postgres:17-alpine`** — matching `mjolnir-postgres`'s exact tag, not
  just "some 17," so the two are genuinely identical, not coincidentally
  compatible.
- **A new, empty named volume** for the v17 data directory
  (`stabbur_stabbur-pg-data-17` or equivalent) — Postgres major versions
  are not binary-compatible on-disk, so this is a fresh initialization,
  not an in-place file-level upgrade (`pg_upgrade` was considered and
  rejected for a dataset this size, see `design.md`).
- **Live data migrates via dump/restore** — the exact mechanism already
  built and verified for `git-backup` (`pg_dump` the old container,
  stand up the new one, `psql` the dump back in). No new tooling.
- **The old `postgres:16` volume is kept, unused, for a cool-down period**
  rather than deleted immediately — cheap insurance against a migration
  surprise, consistent with this project's general bias toward
  reversibility over immediate cleanup.
- This change's own tasks are almost entirely **operator-executed, by
  design** (stopping the live service and migrating real data is not
  something to automate on a first run) — see `tasks.md`.

## Capabilities

### New Capabilities
- `postgres-version`: the invariant that `stabbur`'s and `mjolnir`'s
  Postgres instances run the same major version, and why that's load-
  bearing for the backup service rather than cosmetic.

### Modified Capabilities
<!-- None. -->

## Impact

- `stabbur/compose.yaml` — image tag, volume name.
- No application code changes — `stabbur-backend`'s `DATABASE_URL` already
  points at the service name (`stabbur-postgres`), not a version-specific
  detail.
- Blocks `tun`'s `compose-backup-service` change from needing a
  dual-client-version image — not a hard dependency (that change can still
  support two versions if this one is deferred), but doing this first
  removes a whole category of complexity from it.
