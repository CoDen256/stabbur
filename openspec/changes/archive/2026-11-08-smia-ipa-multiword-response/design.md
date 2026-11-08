## Context

smia's `ipa-api` spec (post-`fad6764`) now specifies a two-stage lookup
above the provider layer: the caller's whole `text` is tried as a phrase
first — applying smia's own `norwegian-input` query variants, so a leading
`en`/`ei`/`et`/`å` is stripped into an *additional* variant rather than a
rewrite — and only on a miss is the input tokenized and each token looked
up separately.

Two consequences land on stabbur:

1. The response shape is a union, and stabbur's single-shape reader fails
   closed on the new arm (see proposal).
2. stabbur no longer needs to strip `"å "` before an IPA lookup. That part
   is **not** handled here — it belongs with the query-sourcing rework in
   `editor-session-hygiene`, which owns the `lemma`/`text` binding. This
   change is deliberately scoped to response *reading* only, so the
   regression fix can land without waiting on the UX work.

A caveat worth recording, because it is easy to over-generalise: smia's
`query_variants` is applied by the `/ipa` **route**, and separately by the
`ordbank` (inflections) and `dictcc_api` (translations) **adapters** — not
universally. `/tts`, `/examples`, and the other inflections/translations
adapters do not strip prefixes. "smia normalises Norwegian input now" is
true for `/ipa` and false in general; stabbur must not assume otherwise.

## Goals / Non-Goals

**Goals:**

- Read both `mode` arms correctly, so a multi-word transcription lookup
  stops silently reporting "no results".
- Make a partially-resolved phrase legible: which tokens resolved, which
  did not.
- Respect smia's deliberate refusal to assemble a transcription when doing
  so would require a choice.

**Non-Goals:**

- No change to which string is sent as the IPA query. `editor-session-hygiene`
  owns that.
- No stabbur-side tokenization. If stabbur ever needs to know a phrase's
  tokens, it reads them from `tokens[].text` — smia's tokenizer is
  authoritative (it keeps hyphenated compounds whole, drops digit-only
  tokens, and keeps `seg` as a standalone token; reimplementing that in JS
  would drift).
- No stabbur-side join when `joined` is absent. This is the whole point of
  D2 below.
- No change to `/ipa`'s variety rendering (already correct).

## Decisions

### D1 — Dispatch on `mode`, and treat a missing `mode` as `phrase`

The IPA result handler branches on `body.mode`. A response with no `mode`
key is treated as `phrase`, which makes the change backward-compatible with
a smia deployed before `a044ac0` — relevant because stabbur and smia deploy
independently and there is no version negotiation between them.

Rejected: sniffing on the presence of `tokens` instead of reading `mode`.
`mode` is the field smia specifies as the discriminator; keying off the
payload's shape would re-derive what the contract already states.

### D2 — When `joined` is absent, stabbur offers no whole-phrase fill

smia's spec is unusually explicit here, and the reasoning transfers
directly: `joined` is omitted precisely when some token has zero candidates
or more than one, i.e. when picking a single phrase transcription requires
a judgement. If stabbur joined the tokens anyway it would be inventing the
very answer smia declined to invent, and — worse — presenting a guess in a
field the operator reviews at a glance and is likely to accept.

So: `joined` present → a single "Use" that fills `transcription` with it.
`joined` absent → no phrase-level fill offered at all; the operator uses
tokens individually or types the transcription.

This is the one place where doing less is the requirement rather than a
simplification.

### D3 — `joined` is visually distinguished from a real phrase lookup

smia permits `joined` as "the single permitted exception to this
capability's rule that every returned transcription is a real lookup", and
requires it not be presented as the phrase's actual pronunciation. A
`mode: "phrase"` result is a real entry someone recorded; a `joined` string
is citation forms glued together, which for Norwegian is frequently wrong
at the phrase level (tone and stress shift across a compound or particle
verb in ways per-word citation forms do not capture).

The UI therefore labels it as assembled-from-single-words rather than
showing it in the same visual position and weight as a phrase candidate.

### D4 — Per-token rows reuse `renderIpaCandidate` unchanged

Each `tokens[i].candidates` entry has the same `{ipa, variety?}` shape as a
phrase candidate, so the existing renderer applies as-is. The only new
markup is the token grouping around it. This keeps "Use" semantics
identical (write into `transcription`, mark used) and avoids a second
candidate renderer drifting from the first.

Open question deferred to implementation: whether a token's "Use" should
*replace* the transcription field or *append* to it. Replacing is
consistent with every other "Use" in the editor; appending would let the
operator build a phrase token by token. Appending interacts with the
translations merge-mode setting in `operator-settings` and is better
decided once that setting exists — so this change ships the consistent
behaviour (replace) and leaves the richer option to a follow-up.

## Risks

- **Unverifiable without a live smia.** stabbur has no frontend test suite
  and the per-word arm requires a provider that genuinely lacks a phrase
  entry. The verification tasks are written as explicit manual steps with a
  named reproduction case (`legge til`), consistent with how previous
  note-editor changes recorded what was and was not verified.
- **Backward compatibility is assumed, not tested.** D1's missing-`mode`
  fallback protects an older smia, but nothing in CI exercises it.
