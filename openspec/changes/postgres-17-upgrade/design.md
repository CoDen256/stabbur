## Context

Read `tun/docs/07-decisions.md` D129/D130 (the backup script's two
found-live bugs) before touching this — they're the direct motivation for
wanting one Postgres version, not two, feeding the backup mechanism. Read
`stabbur/compose.yaml`'s existing `stabbur-postgres` service and its
volume-naming comment (explicit `name:` so the volume is identical whether
brought up standalone or via `tun`'s `include:` — the same reasoning
applies to whatever the new v17 volume is named).

Confirmed directly:
- `postgres-client-16` and `postgres-client-17` coexist cleanly side by
  side on Debian via the official PGDG apt repo, each at its own versioned
  path (`/usr/lib/postgresql/16/bin/pg_dump`, `.../17/bin/pg_dump`) —
  tested live. So the dual-version path is a real, working fallback if this
  change is ever deferred; it's being avoided here for simplicity, not
  because it doesn't work.
- `stabbur-backend`'s `DATABASE_URL` already addresses Postgres by service
  name (`stabbur-postgres`) with no version-specific connection detail —
  confirmed in `compose.yaml`; the application side needs zero changes.

## Goals / Non-Goals

**Goals:**
- `stabbur-postgres` and `mjolnir-postgres` run the identical Postgres
  image tag.
- Zero data loss, zero unplanned downtime beyond the deliberate migration
  window.
- Reuse the exact dump/restore mechanism already built and verified for
  `git-backup` — no new migration tooling.

**Non-Goals:**
- `pg_upgrade` (in-place binary upgrade) — faster for large datasets, but
  more operationally complex (needs both version binaries present
  simultaneously against the same data directory, more failure modes) for
  a dataset this small. Dump/restore is simpler and already proven.
- Automating the migration itself — this is a one-time, operator-executed
  procedure against live production data, not something to script and run
  unattended on a first attempt.
- Any change to `stabbur-backend`'s own code or its database schema.

## Decisions

### D-U1 — Dump/restore, not `pg_upgrade`

`pg_upgrade` requires both the old and new `postgres` binaries available
against the same data directory and is meaningfully more moving parts to
get right for a one-time, small-dataset migration. A plain `pg_dump` /
`psql`-restore cycle is simpler, is the exact mechanism `git-backup`
already exercises and has already been verified correct in this project
(the scratch-restore test performed while building that change), and costs
nothing extra for a database this size (seconds, not hours).

### D-U2 — A new volume name, old one kept temporarily

Postgres major versions use incompatible on-disk formats — starting the
new `postgres:17-alpine` container against the existing `stabbur_stabbur-
pg-data` volume would simply fail to initialize correctly. A new,
explicitly-named volume (e.g. `stabbur_stabbur-pg-data-17`) is the target;
the old volume is left alone (not deleted) for a cool-down period so a
migration problem discovered after the fact still has the original data to
fall back to.

### D-U3 — Image tag matches `mjolnir-postgres` exactly, not just "same major"

`postgres:17-alpine`, not `postgres:17`. The goal is a single, interchangeable
client-tooling story for the backup service, not merely "close enough" —
matching the exact tag removes any remaining doubt about patch-level
behavior differences.

## Risks / Trade-offs

- **A brief write-downtime window** while `stabbur-backend` is stopped for
  the dump — acceptable for a solo-operator project; schedule it when not
  actively authoring notes.
- **The dump/restore step is manual** (Non-Goal) — matches this project's
  established pattern for anything touching live production data directly
  (same treatment as every patch-assembly/install step throughout this
  project).
- **Disk usage briefly doubles** (both volumes present during the
  cool-down period) — negligible at this project's actual data size.

## Migration Plan

See `tasks.md` for the exact operator-executed sequence. In outline: stop
the app → dump the old version → bring up the new version against a fresh
volume → restore → verify row counts → restart the app → keep the old
volume around, unused, before eventually removing it.

## Open Questions

- How long to keep the old `postgres:16` volume before removing it?
  Left to operator judgment — no fixed window decided here.
