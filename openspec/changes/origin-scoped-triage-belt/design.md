## Context

The pieces this change needs mostly exist already:

- `GET /api/notes/authoring` filters on `status`, `type`, `pos`,
  `grammar_rule_id`, `q`, and — since `note-origin-provenance` — `origin`,
  and sorts through a fixed `AUTHORING_SORTS` map that already includes
  `updated_asc`.
- `origin` is a non-null column constrained to `manual`/`capture`/`import`,
  with storage-level checks tying `capture_id` and `import_ref` to their
  origins.
- Every suggestion kind already has a working provider lookup; what is
  missing is an orchestration that runs several without the operator
  clicking through each.

So the queue itself is close to free. The genuinely new decisions are what
"send to back" means in storage, where the prefill walk runs, and how the
audio paste box generalises.

The mockup `assets/triage-belt-mock.html` is the agreed visual design and
the source of truth for layout and interaction, mirroring how
`lemma-first-suggestions` treated `assets/lemma-first-suggestions-mock.html`.
It also covers the `operator-settings` page and the editor's fill control,
since those were designed in the same pass.

## Goals / Non-Goals

**Goals:**

- Review a long queue of drafts without a navigation step between notes.
- Keep imported and hand-authored review separate, because they need
  different attention.
- Arrive at each note already filled in, with provenance visible.
- Three verdicts in a fixed position, reachable by keyboard.

**Non-Goals:**

- **Not a replacement for the note editor.** The editor keeps every
  capability it has and remains how a single note is opened. The belt is an
  additional tab.
- No new note status. `status` stays `draft`/`ready` (CLAUDE.md's hard
  boundary); accepting a note sets `ready`, and nothing in triage
  introduces a third state.
- No Mjølnir concepts. This reviews **notes**. The word "card" does not
  appear in this capability.
- No automatic acceptance. Prefilling a field is not reviewing it; only an
  explicit verdict advances a note to `ready`.
- No cross-origin queue. Reviewing "everything at once" is deliberately not
  offered — see D2.

## Decisions

### D1 — The belt is a new capability and a new tab, not a mode of the editor

Triage and editing are different activities: editing is "I want to change
this note", triage is "I want to clear this queue". They share a form but
not a shape — triage has a position, a remaining count, verdicts, and an
advance step, none of which make sense when you opened one note on purpose.

Modelling triage as a mode of the editor would put queue state into a
surface that has no queue. So: new `note-triage` capability, new route,
new rail entry, reusing the editor's field components.

### D2 — The queue is scoped to exactly one origin at a time

`origin` partitions every note into `manual`, `capture`, or `import`, and
the three need different review:

| | `import` | `manual` |
|---|---|---|
| Arrives | thousands at once | one at a time |
| Fields | mostly empty | mostly considered |
| Attention | fast yes/no, heavy prefill | careful, light prefill |
| Typical verdict | accept or delete on sight | accept after editing |

A mixed queue forces the operator to switch between those two modes
unpredictably, which is exactly the cost the belt exists to remove.

Rejected: an "all origins" option. It is cheap to add and would quietly
become the default, re-creating the mixed queue. If it turns out to be
wanted, it is one line — but it should be added because it was missed, not
shipped because it was easy.

### D3 — Prefer reusing `updated_at` ordering for deferral over a new column

"Send to back" needs to survive a page reload, so it cannot be a
client-side array. Three options:

| Approach | Schema | Survives reload | Cost |
|---|---|---|---|
| Session array in JS | none | ✗ | deferral lost on refresh |
| **Order by `updated_at` asc; deferring touches it** | **none** | **✓** | conflates "deferred" with "edited" |
| `triage_deferred_at` column | +1 col | ✓ | a speculative column |

The middle option is preferred for a first implementation. `AUTHORING_SORTS`
already offers `updated_asc`, so the queue is expressible today as
`?status=draft&origin=<x>&sort=updated_asc`, and deferring is an ordinary
save — which the belt performs anyway, since deferral keeps edits.

The conflation is real but small: in this queue, editing a note and
deferring it are nearly the same act, because the belt saves on deferral.
`db/models.py` explicitly resists speculative columns, and this avoids one.

Recorded as reversible: if the conflation bites — most likely if the
operator wants "notes I deliberately set aside" as a distinct view — the
fallback is a `triage_deferred_at` column, and the spec below is written in
terms of *behaviour* (a deferred note returns at the end) rather than
mechanism, so it does not need rewriting.

### D4 — The prefill walk runs in the browser, as N ordinary lookups

`operator-settings` narrows `smia-enrichment`'s no-fallback rule to permit
an operator-ordered walk, on three conditions: operator-initiated,
individually pass-through, and the answering provider named. All three are
satisfiable only if the walk is client-side.

Putting the chain in `routes/enrich.py` would rebuild the exact layer the
original rule forbids, inside the module whose docstring forbids it ("no
retry, no fallback, no reinterpretation"). So `routes/enrich.py` gains no
chain logic; the browser issues N ordinary `POST /api/enrich/<kind>` calls
and stops at the first that answers.

This also makes provenance free: the browser knows which call answered, so
naming the provider per field needs no extra plumbing.

### D5 — Prefill never overwrites a value that is already there

A field that is non-empty — because the operator typed it, or because the
import carried it — is left alone. Prefill fills gaps; it does not express
an opinion about existing content.

This is what makes automatic-on-open safe. If prefill could overwrite, the
operator would have to inspect every field on every note to check nothing
had been replaced behind them, which costs more than the prefill saves.

### D6 — Prefill timing is a setting, with both options genuinely useful

Automatic-on-open is faster for a bulk import where most notes will be
accepted. On-demand avoids spending provider lookups (and smia cache rows)
on notes that will be deleted on sight — plausible for a noisy import.

Neither dominates, so it is a setting rather than a decision. It lives in
`operator-settings` with the other preferences.

### D7 — Audio capture discriminates on the link, not on a provider row

The two existing endpoints are provider-named but provider-independent:

| Endpoint | What it actually does | Contacts Forvo/filmot? |
|---|---|---|
| `/api/enrich/manual-link/forvo` | fetch a direct audio URL, store bytes | no |
| `/api/enrich/manual-link/filmot` | clip a YouTube URL at `?t=` via yt-dlp | no |

Both already discriminate internally: `_validate_fetch_url` rejects unsafe
schemes and private addresses, `_parse_youtube_timecode` reads `?t=`/`?start=`.
A single link-shaped endpoint routes on those existing helpers, and the
provider-named routes stay as aliases so the per-provider paste-back rows
keep working unchanged.

**The YouTube arm is known-blocked.** `manual-link-audio-capture`'s spec
records it as implemented but failing against real YouTube after several
rounds of live debugging (archived tasks 6.3). Generalising the paste box
makes that failure *more* prominent, not less — it moves from a filmot row
to the main audio affordance. The UI therefore marks the YouTube path as
known-blocked rather than presenting it as working, and the Forvo-style
direct-audio path remains the only confirmed one.

### D8 — Accept is the only path to `ready`

Accepting sets `status=ready` and advances. Skip advances without writing.
Send-to-back saves edits and requeues. Delete follows the existing
tombstone rule — a `draft` note is hard-deleted, which is every note in
this queue by construction, so triage never creates tombstones.

No verdict introduces a status beyond `draft`/`ready`, and nothing here
tracks whether a downstream consumer took the note — that remains outside
stabbur entirely.

## Risks

- **The belt's position indicator can mislead.** A queue where deferred
  notes return at the end is not a line the operator walks once, so a
  strict position-of-N reads as more precise than it is. The mockup shows a
  remaining count plus a deferred count rather than a single percentage;
  verification should check it still reads honestly after several
  deferrals.
- **Automatic prefill on a large import is a lot of provider traffic.**
  Mitigated by smia's lookup cache and by the on-demand setting, but a
  first run over thousands of notes will be slow and should be tried on a
  small origin before a large one.
- **Deferral conflation** (D3) is accepted deliberately and may need the
  column after all.
- **Keyboard verdicts near destructive actions.** Delete is a verdict with
  a key binding, in a flow designed for speed. It should not sit next to
  accept in the key layout, and an accidental delete of a `draft` is
  unrecoverable (hard delete, by the existing permanence rule).
