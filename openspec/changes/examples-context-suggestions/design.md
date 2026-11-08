## Context

smia's `examples-api` offers four providers of two genuinely different
kinds, and the difference matters to the operator rather than being an
implementation detail:

```
  dictionary          ordbokene   live article API, examples under a definition
                      kaikki      local dump, senses[].examples[]
                          → carry `sense`: which meaning this illustrates

  corpus              tatoeba     imported Norwegian Bokmål sentence export
                      leipzig     Leipzig Corpora Collection, several corpora
                          → carry `source`: which dataset/corpus it came from
```

A dictionary example is short, chosen to illustrate a sense, and often
slightly artificial. A corpus sentence is naturally occurring, matched
against any inflected form of the query (smia expands forms through its
imported inflection table, deliberately avoiding a stemmer so that
`bok`/`bøker` and `komme`/`kom` resolve), and ranked for length and
completeness. Which one a learner wants depends on the word.

Two constraints from smia's spec shape stabbur's side:

- **No translations.** A candidate carries Norwegian text only; smia
  discards any translation its source happened to hold, because
  "translation is `/translations`' concern". stabbur must not present an
  example as a translation candidate or try to pair the two.
- **`limit` participates in cache identity.** Requests differing only in
  `limit` are distinct cache resources. Asking for 10 after asking for 3 is
  a fresh lookup, not a widening of the first.

## Goals / Non-Goals

**Goals:**

- `context_text` gets the same suggestion affordance as every other field.
- A candidate's provenance is visible, so the dictionary/corpus distinction
  is available to the operator rather than flattened.
- The operator can ask for more candidates when the default three are
  unusable.

**Non-Goals:**

- No automatic filling of `context_text`. The standing editor rule —
  suggestions fire only on explicit operator action — applies unchanged.
  Prefill behaviour, if any, belongs to `origin-scoped-triage-belt`.
- No translation of an example. smia deliberately strips translations; the
  editor does not reintroduce them by pairing an example with a
  `/translations` lookup.
- No stabbur-side ranking or filtering of candidates. smia already ranks
  corpus matches (short, complete, few entities, no URLs, no multi-sentence
  lines) and returns them in its chosen order.
- No new kind-specific proxy route.

## Decisions

### D1 — `examples` is an ordinary proxied kind, not a special case

`post_enrich` in `routes/enrich.py` already forwards any kind listed in
`ENRICHABLE_KINDS` to `POST /<kind>` on smia with the body passed through.
`/examples` is a plain JSON lookup with the same contract, so adding the
string to the tuple is the whole backend change.

The tuple's existing comment explains that `/stt` is excluded because it
has "no corresponding note field today". `examples` is the opposite case —
`context_text` is exactly that field — so the stated rule admits it without
being bent.

### D2 — Query with `text`, consistent with the other non-inflection kinds

`editor-session-hygiene` establishes that `inflections` reads `lemma` and
everything else reads `text`. `examples` joins the majority: an example
sentence is wanted for the expression as written.

This is also the better match for smia's behaviour. Corpus providers
expand the query through the inflection table themselves, so sending the
phrase rather than a bare headword loses nothing, while sending a bare
headword for a particle verb would lose the particle.

Caveat: smia's `query_variants` prefix-stripping is **not** applied to
`/examples` (it is applied by the `/ipa` route and the `ordbank` and
`dictcc_api` adapters only). A leading `å`/`en` in `text` therefore reaches
the examples providers unstripped. Nothing here compensates for that —
`text` is not expected to carry an article or infinitive marker — but it is
recorded so a future reader does not assume smia normalises everywhere.

### D3 — Show `source` and `sense`, and do not invent them

Both fields are optional, and smia is explicit that a provider "SHALL omit"
either rather than filling a placeholder. So stabbur shows each only where
present, and shows nothing — not "unknown", not an empty label — where
absent. An absent `sense` on a corpus sentence is correct and should not
look like missing data.

### D4 — `limit` is an explicit operator control, not a silent default

Because `limit` is part of the cache key, a "show more" that re-requests
with a higher limit is a genuine second lookup rather than a cheap
expansion. That is acceptable but should not be hidden: the control is
explicit, and the default stays at smia's own 3.

Rejected: always requesting 10 and paginating client-side. It would make
every first lookup more expensive for a case that is usually satisfied by
the first candidate, and it would populate smia's cache with 10-limit rows
nobody asked for.

### D5 — Candidates render as sentences, not as values

Every existing candidate renderer assumes a short single-line value (an IPA
string, a translation, a paradigm cell) laid out in a row with a "Use"
button. An example is a full sentence and will wrap. The renderer therefore
gives the text its own line above the metadata and action rather than
reusing the single-row layout, which would either truncate or break the
row.

## Risks

- **Panel density.** `context_text` sits lower in the form, and four
  providers × up to three multi-line sentences is a tall panel. Mitigated
  by the default limit of 3 and by panels starting closed
  (`editor-session-hygiene`), but worth a look in verification rather than
  assuming.
- **Corpus quality is unverified from stabbur's side.** smia's ranking
  rules are specified and tested there; stabbur displays whatever arrives.
  If candidates turn out to be poor in practice, the fix belongs in smia's
  ranking, not in stabbur filtering them after the fact.
- **`leipzig` and `tatoeba` are table-backed** and report record counts
  through smia's provider catalogue. A configured-but-unimported provider
  will answer with an empty candidate list rather than an error, which can
  read as "no examples for this word". Surfacing the catalogue's record
  count would distinguish the two, but that is a provider-catalogue
  concern and is not in scope here.
