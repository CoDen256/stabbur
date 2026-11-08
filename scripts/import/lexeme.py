"""
scripts/import/lexeme.py — the lexeme signature builder (design D3, task
4.4) and the form->lemma map it depends on (design D4).

Shared between `key` (signatures for import candidates) and the stock
known-set extractor (signatures for already-known material) — the whole
point of D3 is that both sides of the auto-skip comparison must be built
the same way, or "exact signature match" doesn't mean anything.

signature = (head_lemma, ordered_particles, reflexive, obligatory_complements)

No smia call anywhere in this module (task 4.4) — lemma resolution comes
only from inflection data already parsed in `normalized.inflections_json`
and `normalized.notation_json` (section 3), plus the stock bundle's own
C03-style tense-exercise answers (design D4's last data source).
"""

from __future__ import annotations

import json
import re
import sqlite3

# Separable verb particles — a closed, hand-maintained list (not learned),
# matching design D3's worked examples (legge til, legge om, bytte ut, ...).
PARTICLES = frozenset(
    {
        "til",
        "opp",
        "ut",
        "med",
        "om",
        "fram",
        "frem",
        "bort",
        "sammen",
        "igjen",
        "inn",
        "ned",
        "over",
        "gjennom",
        "etter",
        "av",
        "på",
        "fra",
        "unna",
        "tilbake",
        "forbi",
        "rundt",
    }
)

REFLEXIVE_PRONOUNS = frozenset({"seg"})

_INFINITIVE_MARKER_RE = re.compile(r"^å\s+", re.IGNORECASE)
# A leading indefinite article (en/et/ei) is grammatical marking on the
# noun that follows, not a separate word — strip it the same way the
# infinitive marker is stripped, so "et år" keys on "år", not on "et" as
# if it were the head. Only when followed by more text: a bare "en" on
# its own is the numeral "one" and must keep its own signature.
_INDEF_ARTICLE_RE = re.compile(r"^(en|et|ei)\s+(?=\S)", re.IGNORECASE)
_TOKEN_CLEAN_RE = re.compile(r"^[^\wæøåÆØÅ]+|[^\wæøåÆØÅ]+$")


def _clean_token(token: str) -> str:
    return _TOKEN_CLEAN_RE.sub("", token).lower()


def build_signature(text: str, lemma_map: dict[str, str]) -> tuple[str, tuple[str, ...], bool, tuple[str, ...]] | None:
    """Returns None for empty/whitespace-only text. Otherwise a 4-tuple:
    (head_lemma, particles, reflexive, complements) per design D3.

    Particles and a reflexive pronoun are recognised only in the position
    immediately after the head — this is what keeps `legge til noen i
    kopi` (particle, then complement) distinct from a candidate that
    happens to contain "til" later as part of an unrelated complement."""
    if not text or not text.strip():
        return None

    text = _INFINITIVE_MARKER_RE.sub("", text.strip())
    text = _INDEF_ARTICLE_RE.sub("", text)
    raw_tokens = text.split()
    if not raw_tokens:
        return None

    head_raw = _clean_token(raw_tokens[0])
    head_lemma = lemma_map.get(head_raw, head_raw)

    particles: list[str] = []
    reflexive = False
    i = 1
    while i < len(raw_tokens):
        tok = _clean_token(raw_tokens[i])
        if not particles and not reflexive and tok in REFLEXIVE_PRONOUNS:
            reflexive = True
            i += 1
            continue
        if tok in PARTICLES:
            particles.append(tok)
            i += 1
            continue
        break

    complements = tuple(_clean_token(t) for t in raw_tokens[i:] if _clean_token(t))
    return (head_lemma, tuple(particles), reflexive, complements)


def surface_tokens(text: str) -> tuple[str, ...]:
    """The candidate's own cleaned surface tokens, in order, after stripping
    the infinitive marker and a leading indefinite article the same way
    `build_signature` does — but *not* split into head/particles/complements.

    Used by D13 attestation matching (judge.py): a multiword candidate is
    known only if this exact token sequence is itself a member of
    `stock.build_known_ngrams`'s output, and a single-word candidate's own
    token (after lemma resolution) is checked against `KNOWN_TOKENS`."""
    if not text or not text.strip():
        return ()
    stripped = _INFINITIVE_MARKER_RE.sub("", text.strip())
    stripped = _INDEF_ARTICLE_RE.sub("", stripped)
    return tuple(_clean_token(tok) for tok in stripped.split() if _clean_token(tok))


def signature_key(signature: tuple) -> str:
    """A stable string form of a signature, for use as a SQL grouping/join
    key (`signature.signature_key`, `verdict.signature_key`, ...)."""
    head, particles, reflexive, complements = signature
    return json.dumps([head, list(particles), reflexive, list(complements)], ensure_ascii=False)


# ---------------------------------------------------------------------------
# Form -> lemma map (design D4)
# ---------------------------------------------------------------------------

_VERB_INFLECTION_KEYS = ("presens", "preteritum", "perfektum")


def _last_word(phrase: str) -> str:
    """`"har vært"` -> `"vært"` — auxiliary verbs aren't part of the lemma
    being resolved, but mapping only the last word also gives the aux-less
    form a path to the same lemma."""
    words = phrase.strip().split()
    return words[-1] if words else phrase


def protected_identities(conn: sqlite3.Connection) -> frozenset[str]:
    """Every single-token headword that appears as its own `normalized.text`
    somewhere — used to stop an inflected/derived form from a *different*
    word claiming one of these as its lemma (see
    `build_lemma_map_from_normalized`'s docstring). Exposed separately so
    callers merging in additional lemma sources (the stock C03 bootstrap,
    `key.build_combined_lemma_map`) can apply the same guard."""
    rows = conn.execute("SELECT text FROM normalized").fetchall()
    return frozenset(_clean_token(row["text"]) for row in rows if row["text"] and len(row["text"].split()) == 1)


def build_lemma_map_from_normalized(conn: sqlite3.Connection) -> dict[str, str]:
    """Reads every import source's already-parsed inflection data
    (`normalized.inflections_json`, `normalized.notation_json`) and builds
    surface-form -> lemma. Malformed inflections (`_malformed`, section 3)
    are skipped, not guessed from.

    Homograph guard: a single-token surface form that is itself a genuine
    standalone headword elsewhere in `normalized` (e.g. `når`, `lyst`, each
    its own dictionary entry across multiple sources) is never remapped to
    a *different* lemma just because it happens to also be an inflected
    form of some unrelated word (`når` is also `nå`'s present tense;
    `lyst` is also `lyse`'s past participle). Measured: without this
    guard, freq6k's paradigm mining collapses dozens of genuinely distinct
    closed-class/common words into one, each a case where D6's
    uncertainty-resolves-toward-import invariant would otherwise be
    violated by a wrongful auto-skip. The guard is a plain identity check,
    not disambiguation by meaning — it only refuses to let an *inflected*
    mapping overwrite a token's *own* standalone identity; it doesn't
    attempt to pick the "right" sense when a form is ambiguous and never
    appears as its own headword."""
    rows = conn.execute("SELECT text, inflections_json, notation_json FROM normalized").fetchall()

    protected = protected_identities(conn)

    form_to_lemma: dict[str, str] = {}

    def _assign(form: str, lemma: str) -> None:
        if form in protected and form != lemma:
            return
        form_to_lemma[form] = lemma

    for row in rows:
        text = row["text"]
        inflections = json.loads(row["inflections_json"])
        notation = json.loads(row["notation_json"])

        if "_malformed" in inflections or "_malformed_labels" in inflections:
            continue

        if "infinitiv" in inflections:
            lemma = _clean_token(inflections["infinitiv"])
            for key in _VERB_INFLECTION_KEYS:
                value = inflections.get(key)
                if not value:
                    continue
                _assign(_clean_token(value), lemma)
                _assign(_clean_token(_last_word(value)), lemma)
        elif "sg_indef" in inflections:
            lemma = _clean_token(inflections["sg_indef"])
            for key in ("sg_def", "pl_indef", "pl_def"):
                value = inflections.get(key)
                if value:
                    _assign(_clean_token(value), lemma)
        elif "positiv" in inflections:
            lemma = _clean_token(inflections["positiv"])
            for key in ("nøytrum", "bestemt_flertall"):
                value = inflections.get(key)
                if value:
                    _assign(_clean_token(value), lemma)

        paradigm_forms = notation.get("paradigm_forms")
        if paradigm_forms and text:
            lemma = _clean_token(text)
            for form in paradigm_forms:
                _assign(_clean_token(form), lemma)

    return form_to_lemma
