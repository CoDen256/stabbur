"""
scripts/import/key.py — section 4.4: `normalized` -> `signature`.

Builds the form->lemma map from every import source's own parsed
inflection data (section 3) plus the stock bundle's C03 bootstrap (design
D4's last listed source — see lexeme.py/stock.py), then computes each
normalized candidate's D3 lexeme signature.

This is also where task 3.9's distinct-lexeme assertion actually belongs
(deferred here from `normalize`, see design.md's implementation-correction
note). The count went through three measurements before settling, each one
catching a real bug via task 4.8's skipped-set spot-check rather than
being accepted at face value (see design.md's section 4 correction note
for the full account):

1. First pass: 9,270 — looked like confirmation of design's 9,129
   (within 1.5%), but the skipped-set spot-check (task 4.8) found ~20% of
   auto-skips were wrong: a leading `en`/`et`/`ei` was being treated as
   the signature *head* instead of being stripped like `å` (so `et år`
   became head=`et`, complement=`år` — a different signature from plain
   `år`, inflating the distinct count with spurious article-led
   duplicates).
2. After stripping the article: 7,252 — correctly collapsed those
   duplicates, but surfaced a second bug: the freq6k paradigm miner's
   flat form->lemma map let one word's inflected form overwrite a
   different word's own standalone identity (e.g. `når` is also `nå`'s
   present tense, so `når` silently became `nå`'s lemma).
3. After guarding standalone headwords from being overwritten (`lexeme.
   protected_identities`): **7,582**, the number asserted below.

7,582 is farther from design's 9,129 than the first, buggy measurement —
that's expected, not a regression: the first number was inflated by two
now-fixed double-counting bugs, and the true count also absorbs
irreducible homograph collisions the D3 signature can't distinguish
(`tre` the tree / the numeral "three" / "to step" all collapse to one
signature, since D3's tuple carries no part-of-speech). 7,582 is asserted
as the measured, reproducible baseline going forward.

**review-queue-filters task 2.1/2.3 re-measurement:** `normalize.py` now
re-types 54 `core6k` rows whose single-word field actually held a sentence
(`Jeg lærer norsk.`, `Hvor er nærmeste sykehus?`, …) from `word` to
`listening` — so they're excluded from this count the same way every other
`listening` row already is. Measured after that change: **7,534** (down
48 from 7,582, not the full 54, since a few of those sentences shared a
signature with another `word` candidate). Same measure-and-document
convention as the count above.
"""

from __future__ import annotations

import json
import sqlite3

import lexeme
import stock

# Measured baseline (see module docstring for how this compares to
# design.md's 9,129 and why `listening` is excluded; review-queue-filters
# task 2.1 moved 48 of these out via the core6k sentence re-routing).
DISTINCT_LEXEME_SIGNATURE_EXPECTED = 7534


class KeyCountMismatch(AssertionError):
    pass


def build_combined_lemma_map(conn: sqlite3.Connection) -> dict[str, str]:
    lemma_map = lexeme.build_lemma_map_from_normalized(conn)
    try:
        cards = stock.load_stock_cards()
    except (FileNotFoundError, ValueError) as exc:
        print(f"key: stock bundle unavailable ({exc}) — lemma map built from import sources only")
        cards = []

    # Same homograph guard as build_lemma_map_from_normalized (see its
    # docstring) — the C03 bootstrap has no visibility into import
    # candidates' own standalone headwords, so it must not be allowed to
    # override one of them either.
    protected = lexeme.protected_identities(conn)
    for form, lemma in stock.bootstrap_c03_lemma_map(cards).items():
        if form in protected and form != lemma:
            continue
        lemma_map[form] = lemma

    return lemma_map


def run(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    import store

    rows = conn.execute("SELECT id, text FROM normalized").fetchall()
    count_in = len(rows)
    lemma_map = build_combined_lemma_map(conn)

    out_rows = []
    for row in rows:
        signature = lexeme.build_signature(row["text"], lemma_map)
        if signature is None:
            continue
        out_rows.append((row["id"], signature))

    store.replace_stage_table(conn, "key")
    for normalized_id, signature in out_rows:
        head, particles, reflexive, complements = signature
        conn.execute(
            """
            INSERT INTO signature (
                run_id, normalized_id, signature_key, head_lemma, particles_json, reflexive, complements_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                normalized_id,
                lexeme.signature_key(signature),
                head,
                json.dumps(list(particles), ensure_ascii=False),
                int(reflexive),
                json.dumps(list(complements), ensure_ascii=False),
            ),
        )
    conn.commit()

    distinct = conn.execute(
        """
        SELECT COUNT(DISTINCT s.signature_key)
        FROM signature s JOIN normalized n ON n.id = s.normalized_id
        WHERE n.note_type != 'listening'
        """
    ).fetchone()[0]
    if distinct != DISTINCT_LEXEME_SIGNATURE_EXPECTED:
        raise KeyCountMismatch(
            f"distinct lexeme signature count: expected {DISTINCT_LEXEME_SIGNATURE_EXPECTED}, got {distinct} "
            f"(design.md's original estimate was 9,129 — see module docstring)"
        )

    count_out = len(out_rows)
    count_discarded = count_in - count_out
    return count_in, count_out, count_discarded
