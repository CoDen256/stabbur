## Context

stabbur is a single-operator authoring tool behind a shared bearer token
(`auth.py`). There is no user model, no session, and no per-user anything —
which makes "operator settings" singular by construction: one record, not
one per account.

The enrichment provider list is **not** stabbur's to own. It comes from
smia's `GET /providers`, proxied at `/api/enrich/providers`, and changes
whenever smia gains an adapter or loses a credential (smia's registry
re-checks each provider's `available` callable on every listing). Any
stored provider preference is therefore a preference *about* a list stabbur
does not control, and must degrade gracefully when that list moves.

This change also has to resolve a direct conflict with an existing
requirement, which is the main reason it carries a design document at all.
`smia-enrichment` says:

> The system SHALL pass through a provider's failure ... and SHALL NOT
> automatically retry the same kind against a different provider.

A "fill from my primary provider, falling back down my order" feature is,
read literally, exactly the prohibited thing. D4 below resolves it.

## Goals / Non-Goals

**Goals:**

- One durable place for operator preferences, in stabbur's own database.
- Provider preference expressed as an order plus enabled flags, per kind.
- Settings that are safe to read before they have ever been written.
- Resolve the no-fallback conflict explicitly, in the spec, rather than by
  implementation convenience.

**Non-Goals:**

- No per-user settings, no auth model change. One operator, one record.
- No prefill behaviour here. *When* primary providers run, and what "fill
  all" does, belong to `origin-scoped-triage-belt`, which is where the
  behaviour is visible. This change only stores which providers are
  primary.
- No settings for anything already decided. `editor-session-hygiene`'s
  form-clearing, panel-collapsing, and per-kind query sourcing are correct
  unconditionally and do not become toggles.
- stabbur does not become a provider registry. It stores ordering and
  enablement, never provider definitions, endpoints, or credentials.

## Decisions

### D1 — One row, not a key/value table

A single settings row with typed columns (plus one JSONB column for the
per-kind provider preference, which is genuinely nested) rather than a
generic `(key, value)` store.

A key/value table looks more flexible but makes every read a multi-row
assembly, makes defaults invisible to the schema, and gives up the
database's ability to say anything about validity. With a handful of known
settings, columns are simply better. This mirrors the repo's existing
preference for real columns over speculative generality (`db/models.py`
resists speculative columns rather than hiding them behind a blob).

### D2 — Defaults live in code, applied on read

The settings row may be absent or partially populated. Reading settings
returns a fully-populated object with code-level defaults filled in for
anything unset, so no caller ever branches on "settings not configured
yet".

Rejected: seeding a row in the migration. A seeded row freezes the
defaults at migration time — changing a default later would then require a
data migration to reach installations that had never touched that setting.
Defaults-on-read means changing a default is a code change.

### D3 — Provider preference is an order plus enabled flags, reconciled against the live catalogue

Stored shape, per kind: an ordered list of provider names, and the set
that are disabled. On read, stabbur reconciles against the current
catalogue:

```
  stored order:      [wikipron, ipadict, nst]
  live catalogue:    [ipadict, kaikki_ipa, nst, wikipron]
                         │
                         ▼
  effective:         [wikipron, ipadict, nst] ++ [kaikki_ipa]
                      └── known, in stored order ──┘  └─ new, appended ─┘
```

- A provider in the stored order that is no longer in the catalogue is
  skipped, not an error, and its position is remembered in case it returns
  (a provider can disappear simply because a token is unset).
- A provider in the catalogue that is not in the stored order is appended
  at the end, enabled. A newly added provider should be available, but
  should not silently become anyone's primary.

The **primary** for a kind is the first enabled provider in the effective
order — derived, never stored separately, so the two cannot disagree.

### D4 — Narrow the no-fallback rule to the proxy, and permit an operator-ordered walk

The existing rule protects something real: stabbur must not paper over a
provider's answer, so that "dict.cc has no entry for this" reaches the
operator as itself rather than as a silently different provider's result.
That protection is about **the proxy's behaviour on a single lookup**.

An operator walking their own configured order is a different act:

| | proxy retry (still forbidden) | operator-ordered walk (permitted) |
|---|---|---|
| Who decided | stabbur, implicitly | the operator, in settings |
| Visible | no — one request, one answer | yes — the result names which provider answered |
| Scope | inside one lookup | across several explicit lookups |
| Can be turned off | no | yes, it is a setting |

So the requirement is modified to forbid the first and permit the second,
with the condition that the answering provider is always named. The
mechanism stays in the browser: N ordinary `POST /api/enrich/<kind>` calls,
each passed through untouched. `routes/enrich.py` gains no chain logic —
putting the walk on the server would rebuild precisely the layer the
original rule forbids, in the module that forbids it.

### D5 — Reversing the empty-override decision, and keeping both

`lemma-first-suggestions` decided a revealed per-provider override starts
empty, "so it reads unambiguously as a different input rather than a copy".
The reasoning was sound and did not survive use: the override is reached
for mostly to *adjust* the shared query, and retyping it is friction.

Making it a setting rather than a flat reversal is a deliberate hedge — the
original argument is good enough that the old behaviour should remain
reachable, and the cost of one boolean is low. The default flips to
prefilled.

Note this interacts with an existing scenario: "Collapsing an override
falls back to the shared query". That stays true — a collapsed override is
not used regardless of what it was prefilled with.

### D6 — Translation merge mode applies at the point of use, not on save

Merge mode changes what "Use" does in the translations panel: append to the
language's existing row separated by ` / `, or add a new row. It does not
rewrite anything already stored, and changing the setting never alters
existing notes. A note whose translations were built under one mode is not
migrated.

Separator is a single ` / ` (spaces either side), matching how smia itself
joins merged `/ipa` varieties — worth being consistent with, since the
operator sees both.

## Risks

- **Modifying a requirement to permit something it forbade** invites the
  reading that the rule was inconvenient rather than wrong. The modified
  text therefore keeps the original prohibition verbatim for the proxy and
  adds the carve-out as a separate, conditioned clause, so the distinction
  is legible in the spec rather than only in this document.
- **Stored preferences referencing a vanished provider.** Handled by D3,
  but the reconciliation is the part most likely to be got subtly wrong —
  particularly "disabled" surviving a disappearance/reappearance cycle. It
  gets its own verification tasks.
- **A settings page invites scope creep.** Every future preference will
  want to live here. The Non-Goals above state which already-decided
  behaviours are deliberately *not* configurable; that list is the defence.
