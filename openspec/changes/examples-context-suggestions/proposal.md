## Why

A note's `context_text` — the sentence showing the word in use — is the one
substantial field with no suggestion support. Every other field has a
provider panel; this one is typed by hand or left empty.

smia has now closed the gap from its side. `POST /examples` shipped in smia
commit `e10272a` (archived as `examples-api`, synced into its `examples-api`
spec), and smia's own spec names the motivation explicitly: it "fills
stabbur's note-editor `context_text`/X-field gap". `examples` is a
registered kind in smia's registry alongside the five stabbur already uses,
so it already appears in `GET /providers`.

stabbur cannot reach it. `routes/enrich.py`'s `ENRICHABLE_KINDS` is a fixed
tuple of `("ipa", "translations", "inflections", "tts")`, so a request for
`examples` is rejected with a 400 before it ever reaches smia.

## What Changes

- **`examples` becomes a proxied kind.** Added to `ENRICHABLE_KINDS`, with
  no other proxy change — it is an ordinary JSON lookup like `ipa` or
  `translations`.
- **A suggest control on `context_text`**, the same combined
  toggle + editable shared query + per-provider rows used everywhere else,
  querying with `text`.
- **Candidates show where they came from.** smia returns
  `{text, source?, sense?}`, and the two optional fields mean different
  things for the two kinds of provider it offers: dictionary providers
  (`ordbokene`, `kaikki`) attach a `sense` naming the definition the
  example illustrates, while corpus providers (`tatoeba`, `leipzig`) attach
  a `source` naming the dataset the sentence came from. Both are shown when
  present rather than flattened away, because choosing between a
  lexicographer's example and a naturally-occurring sentence is exactly the
  judgement the operator is making.
- **A candidate count control.** smia's `limit` defaults to 3 and clamps to
  1–10. stabbur sends an explicit value so the operator can ask for more
  when the first three are unusable.
- **An `examples` entry in the provider-preference settings**, so the kind
  participates in primary-provider selection like every other kind.

## Capabilities

### Modified Capabilities

- `smia-enrichment`: the set of kinds stabbur proxies is requirement-level
  — the spec names them, and `examples` joins them.
- `note-editor`: `context_text` gaining provider-sourced suggestions is a
  new editor behaviour, including how a candidate's provenance is shown.

## Impact

- **stabbur backend** (`routes/enrich.py`): `ENRICHABLE_KINDS` gains
  `"examples"`. No new route — `post_enrich` already handles any listed
  kind generically.
- **stabbur UI** (`ui/index.html`): suggest control and panel markup beside
  `context_text` on both the new-note (`c_`) and existing-note (`e_`)
  forms.
- **stabbur UI** (`ui/ui.js`): `enrichRequestFields` gains an `examples`
  branch sending `{text, lang, limit}`; a candidate renderer showing
  `text` with `source`/`sense` where present; `openSuggestPanel` routes the
  new kind through the existing generic provider-row path.
- **stabbur UI** (`ui/ui.css`): candidate styling for a multi-line sentence
  rather than the short single-value candidates the other kinds return.
- **No schema changes.** `context_text` already exists.
- **Depends on `operator-settings`** for the primary-provider entry. The
  panel itself works without it; only the preference does not.
