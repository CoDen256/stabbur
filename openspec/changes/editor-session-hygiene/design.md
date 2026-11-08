## Context

`lemma-first-suggestions` (archived `2026-11-03`) unified every suggestion
query on `lemma || text`, reasoning that a verb note's `text` is the full
infinitive phrase (`"å spise"`) while `lemma` holds the bare form. That was
right about the problem and wrong about the fix: it assumed one query
serves every kind.

Use showed otherwise. For `å legge til`:

```
  inflections   want  "legge"      — a paradigm lookup on a particle
                                     verb returns nothing
  translations  want  "legge til"  — "legge" alone means something else
  audio         want  "legge til"  — Forvo has the phrase, not the bare verb
  transcription want  "legge til"  — and smia now handles the phrase itself
```

`lemma || text` cannot express that, because it picks one string for all
four. The replacement is not a cleverer derivation but a flatter binding:
each kind names the field it reads.

The transcription case is only settled because smia changed underneath us.
Before `ipa-multiword`, `/ipa` took a single wordform and a phrase query
would simply miss; stabbur would have needed to split and join the phrase
itself. smia now does the whole-phrase attempt and the per-word fallback
above its provider layer, so `text` is a legitimate transcription query.
Reading that two-armed response is `smia-ipa-multiword-response`'s job, not
this change's — but this change depends on it having landed, or multi-word
transcription queries will render as "no results".

## Goals / Non-Goals

**Goals:**

- One field per kind, stated plainly, with no fallback chain to reason
  about.
- `lemma` populated without a button press, and still fully editable.
- A note's form and panels belong to that note and do not outlive it.
- Re-running providers after editing a query is one visible click and
  actually re-queries.

**Non-Goals:**

- No `"å "` stripping anywhere in stabbur. The marker is not expected in
  `text`, and smia strips a leading `en`/`ei`/`et`/`å` into an additional
  variant where it matters. Note this is *not* universal in smia — see D2's
  caveat — but it is not stabbur's job to compensate.
- No settings for any of this. Whether prefill runs on open or on a button,
  and which providers are primary, belong to `operator-settings`. This
  change hardcodes the one sensible behaviour for each item above.
- No change to how candidates are rendered. That is
  `smia-ipa-multiword-response`.
- No triage-specific behaviour. `origin-scoped-triage-belt` consumes these
  rules; it does not alter them.

## Decisions

### D1 — Bind each kind to a field, rather than deriving a query

`inflections` reads `lemma`. `ipa`, `tts`, `translations` read `text`. No
`||`, no first-token extraction at query time, no part-of-speech check.

Rejected: keeping `lemma || text` for the three non-inflection kinds as a
safety net. A fallback hides the case it fires in — a note with an empty
`text` is a note that should fail loudly, not quietly query something else.
The existing `TYPE_VISIBLE_FIELDS` logic already guarantees `lemma` is only
present for `type=word`, so the inflections binding is safe without a type
guard.

Rejected: a derived "headword" string (first token of `lemma`) feeding
transcription separately from a "phrase" string feeding audio. This was
explored and discarded as more model than the problem needs, once smia's
multi-word `/ipa` removed the reason transcription wanted a single token.

### D2 — Reactive `lemma`, with a dirty flag, and no button

`lemma` follows the first whitespace-separated token of `text` as the
operator types, until the operator edits `lemma` directly — after which it
is theirs for the rest of that note. Loading a different note clears the
flag.

This is the same pattern `syncSuggestQueries` already implements for
suggest-control queries (`input.dataset.dirty`), so it is an existing idiom
in this file rather than a new one.

Rejected: keeping the button and changing its rule from "strip å" to "first
token". A button the operator must remember to press is the complaint that
produced this change; and with `å` gone from `text`, the first-token rule
is right often enough that making it the default costs nothing when wrong
(the field stays editable).

Caveat worth recording, because it is easy to over-trust: smia's
`query_variants` prefix-stripping is applied by the `/ipa` **route** and by
the `ordbank` and `dictcc_api` **adapters** only. `/tts`, `/examples`, and
the remaining translations/inflections adapters do not strip. "smia
normalises Norwegian input" is true for transcription and false in general.
Nothing here depends on it, but a future change should not assume it.

### D3 — Reset is a clearing function, not a page reload

The new-note form is cleared by an explicit `resetCreateForm` that zeroes
every field, drops each suggest control's value *and* its `dirty` flag,
clears `newNoteAudioFromSuggest`, and resets the file input. It runs after
a successful create and on entering the new-note route.

Rejected: re-rendering the form from a template. The form is static markup
in `index.html` with handlers bound once at load; re-rendering would
require rebinding and risks duplicate listeners — a known hazard in a file
that wires listeners at module scope.

### D4 — Panels close *and* empty on note load

Collapsing alone is insufficient: a collapsed panel retains the previous
note's `innerHTML`, so reopening it shows stale candidates for a fraction
of a second before the new lookup resolves — or indefinitely, if the new
lookup fails. So both the `open` class and the content are cleared.

This extends the existing `resetSuggestQueries(prefix)` hook rather than
adding a parallel one; it already runs on note load and already walks every
control for the prefix.

### D5 — An explicit re-run forces a fresh lookup

smia caches every lookup by `(kind, provider, input)`. Re-firing a provider
with an *unchanged* query therefore returns the cached row — which is
correct and desirable for an ordinary panel open, and actively wrong for a
re-run the operator pressed *because* they want the provider consulted
again.

So: opening a panel does not force; the explicit `⟳` (panel-level and
per-provider) does. `routes/enrich.py` forwards the flag when the client
sends it, which keeps the proxy a pass-through — stabbur is not deciding to
bypass a cache, it is relaying that the operator did.

smia accepts `forceRefresh` on every kind: `routes/generic.py` takes it as
`force_refresh_param` defaulting to `"forceRefresh"`, and `routes/ipa.py`
reads `body.get("forceRefresh", False)` explicitly.

Open question for implementation: whether editing the shared query and
pressing Enter should also force. It arguably need not — a *different*
query is a different cache key and will miss anyway — so forcing there
would only add load. The tasks treat Enter as non-forcing and `⟳` as
forcing, which is both cheaper and easier to explain.

## Risks

- **Supersedes an archived decision.** `lemma-first-suggestions`' core rule
  is reversed here. The delta spec states the new rule in full rather than
  patching the old wording, so the archived change remains readable as what
  was believed at the time.
- **Reactive `lemma` could surprise on non-verbs.** For a noun note whose
  `text` is a single word, first-token and whole-text are identical, so the
  sync is invisible. For a multi-word `expression`, `lemma` is not a
  visible field at all (`TYPE_VISIBLE_FIELDS`). The exposure is therefore
  narrow, but worth confirming in verification.
- **Hard dependency on `smia-ipa-multiword-response`.** Routing `text` to
  `/ipa` makes multi-word transcription queries common. Without the
  response-shape fix, those render as "no results" — a worse experience
  than today. These two must land in order.
