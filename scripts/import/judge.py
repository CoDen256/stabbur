"""
scripts/import/judge.py — section 4b: `signature` + D13 known-set ->
`verdict`. Rewritten under design D13 (tasks 4b.7, 4b.8, 4b.11); supersedes
the exact-signature-match rule this module used to implement (tasks
4.5-4.8, left in tasks.md section 4 as a record of what was built and what
it cost — see that section's own warning not to use it as a spec).

A candidate is skipped iff (D13's own statement of the rule):
- single-word: its own lemma is in `KNOWN_TOKENS`
- multiword: its own full surface sequence is in `KNOWN_NGRAMS`

Nothing else skips. In particular `note_type == "listening"` no longer
forces an import (task 4b.11, superseding task 4.6's "sentence-shaped"
rule) — a1_31k's sentence candidates are attestation-checked exactly like
single words and phrases; some of them genuinely are attested and must
skip.

There is still no substring, prefix, head-only, or token-subset comparison
anywhere in this module (D3's prohibitions survive D13 verbatim, per
design.md) — the only lookups against the known-set are dict/set
membership checks on a candidate's own full token sequence.

Deny-list ordering (D13.4, task 4b.8): the deny-list is consulted *after*
the known-set check, and only for "weak" single-token evidence (attested
only inside a longer line, never as its own dedicated one-word card) — it
must never override "strong" evidence (`KNOWN_TOKENS_STRONG`, a dedicated
card teaching exactly that word) or a multiword n-gram match. This is the
opposite of the old D5-era ordering, which checked the deny-list *before*
any match and so blocked every one of its entries unconditionally,
including the 11 that stock legitimately teaches as their own cards.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import key as key_stage
import lexeme
import stock

DENYLIST_PATH = Path(__file__).resolve().parent / "denylist.json"
SKIPPED_REVIEW_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "import" / "skipped_review.jsonl"


def load_denylist() -> frozenset[str]:
    data = json.loads(DENYLIST_PATH.read_text(encoding="utf-8"))
    return frozenset(data["lemmas"])


def judge_one(
    text: str,
    signature: tuple,
    denylist: frozenset[str],
    known_tokens: dict[str, dict],
    known_tokens_strong: dict[str, dict],
    known_ngrams: dict[tuple[str, ...], dict],
    known_by_head_lemma: dict[str, list[dict]],
    lemma_map: dict[str, str],
) -> tuple[str, str | None, dict]:
    """Returns (verdict, rule, evidence). verdict is "import" or "skip".
    `text` is the candidate's own normalized text (its full surface form,
    pre-signature) — D13 attestation compares surface sequences, not D3
    signatures, which remain in use only for merge (section 5) and for the
    evidence-enrichment flag rules below."""
    tokens = lexeme.surface_tokens(text)
    head = signature[0]

    if len(tokens) == 1:
        lemma = lemma_map.get(tokens[0], tokens[0])
        if lemma in known_tokens_strong:
            return "skip", "attested-token-strong", {"matched": known_tokens_strong[lemma]}
        if lemma in known_tokens:
            if lemma in denylist:
                return "import", "denylist-protected", {"denylisted_lemma": lemma}
            return "skip", "attested-token-weak", {"matched": known_tokens[lemma]}
    elif len(tokens) > 1 and tokens in known_ngrams:
        return "skip", "attested-ngram", {"matched": known_ngrams[tokens], "sequence": list(tokens)}

    same_head = known_by_head_lemma.get(head)
    if same_head and (signature[1] or signature[2]):
        return "import", "same-head-different-particle", {"cf_stock": same_head[0]}

    if len(tokens) > 1:
        all_known = all(
            (lemma_map.get(tok, tok) in known_tokens_strong) or (lemma_map.get(tok, tok) in known_tokens)
            for tok in tokens
        )
        if all_known:
            return "import", "all-tokens-known-phrase-unknown", {"tokens": list(tokens)}

    return "import", None, {}


def run(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    import store

    rows = conn.execute(
        """
        SELECT s.signature_key, s.head_lemma, s.particles_json, s.reflexive, s.complements_json,
               n.note_type, n.text
        FROM signature s
        JOIN normalized n ON n.id = s.normalized_id
        """
    ).fetchall()
    count_in = len(rows)

    lemma_map = key_stage.build_combined_lemma_map(conn)
    cards = stock.load_stock_cards()
    lexicon = stock.build_norwegian_lexicon(conn)
    known_lines = stock.classify_known_lines(cards, lexicon, lemma_map)
    known_tokens = stock.build_known_tokens(known_lines, lemma_map)
    known_tokens_strong = stock.build_known_tokens_strong(known_lines, lemma_map)
    known_ngrams = stock.build_known_ngrams(known_lines)
    known_by_head_lemma = stock.build_known_signatures(known_lines, lemma_map)
    denylist = load_denylist()

    verdicts = []
    skipped_for_review = []
    seen_signature_keys = set()
    for row in rows:
        signature = (
            row["head_lemma"],
            tuple(json.loads(row["particles_json"])),
            bool(row["reflexive"]),
            tuple(json.loads(row["complements_json"])),
        )
        verdict, rule, evidence = judge_one(
            row["text"],
            signature,
            denylist,
            known_tokens,
            known_tokens_strong,
            known_ngrams,
            known_by_head_lemma,
            lemma_map,
        )
        verdicts.append((row["signature_key"], verdict, rule, evidence))
        if verdict == "skip" and row["signature_key"] not in seen_signature_keys:
            seen_signature_keys.add(row["signature_key"])
            skipped_for_review.append({"signature_key": row["signature_key"], "signature": signature, "evidence": evidence})

    store.replace_stage_table(conn, "judge")
    for signature_key, verdict, rule, evidence in verdicts:
        conn.execute(
            "INSERT INTO verdict (run_id, signature_key, verdict, rule, evidence_json) VALUES (?, ?, ?, ?, ?)",
            (run_id, signature_key, verdict, rule, json.dumps(evidence, ensure_ascii=False)),
        )
    conn.commit()

    SKIPPED_REVIEW_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SKIPPED_REVIEW_LOG_PATH, "w", encoding="utf-8") as f:
        for entry in skipped_for_review:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    count_skipped = sum(1 for _, v, _, _ in verdicts if v == "skip")
    count_import = count_in - count_skipped
    print(
        f"judge: {count_skipped} auto-skip ({count_skipped / count_in:.1%}), {count_import} import; "
        f"skipped set dumped to {SKIPPED_REVIEW_LOG_PATH} for spot-check (task 4.8/4b.14)"
    )

    count_out = len(verdicts)
    return count_in, count_out, 0
