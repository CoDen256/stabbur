"""
scripts/import/judge.py — section 4: `signature` + known-set -> `verdict`
(tasks 4.3, 4.5-4.8).

Auto-skip requires an exact signature match (task 4.5) — there is no
other comparison in this module. Substring, prefix, head-only, and
token-subset matching are not merely avoided, they don't exist as code
paths here: the only lookup against the known-set is a dict key equality
check (`signature_key in known_by_signature_key`).

Verdict rules, in order:
1. `listening` (sentence-shaped) candidates always import — signatures
   are meaningless for sentences (design's open question, accepted as
   out of scope here).
2. A denylisted head lemma (task 4.3) always imports, regardless of any
   match — the one override that beats "exact match" is this bigger
   invariant: when the known-set might be wrong, uncertainty resolves
   toward importing (D6).
3. Exact signature match -> skip.
4. Same head, different particles/reflexive -> import, flagged, with a
   `cf. stock` reference to the related known form (task 4.6).
5. Every token independently known but the phrase itself isn't -> import,
   flagged (the idiom case — `bli kvitt`, `bestemme seg`, ...).
6. Otherwise -> import, no evidence (the clean case).
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


def _single_token_signature(token: str, lemma_map: dict[str, str]) -> tuple:
    return lexeme.build_signature(token, lemma_map)


def judge_one(
    signature: tuple,
    note_type: str,
    denylist: frozenset[str],
    known_by_signature_key: dict[str, dict],
    known_by_head_lemma: dict[str, list[dict]],
    lemma_map: dict[str, str],
) -> tuple[str, str | None, dict]:
    """Returns (verdict, rule, evidence). verdict is "import" or "skip"."""
    head, particles, reflexive, complements = signature
    sig_key = lexeme.signature_key(signature)

    if note_type == "listening":
        return "import", "sentence-shaped", {}

    if head in denylist:
        return "import", "denylist-protected", {"denylisted_lemma": head}

    if sig_key in known_by_signature_key:
        return "skip", "exact-match", {"matched": known_by_signature_key[sig_key]}

    same_head = known_by_head_lemma.get(head)
    if same_head and (particles or reflexive):
        return "import", "same-head-different-particle", {"cf_stock": same_head[0]}

    all_tokens = (head,) + complements
    if len(all_tokens) > 1:
        all_known = all(
            lexeme.signature_key((tok, (), False, ())) in known_by_signature_key for tok in all_tokens
        )
        if all_known:
            return "import", "all-tokens-known-phrase-unknown", {"tokens": list(all_tokens)}

    return "import", None, {}


def run(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    import store

    rows = conn.execute(
        """
        SELECT s.signature_key, s.head_lemma, s.particles_json, s.reflexive, s.complements_json, n.note_type
        FROM signature s JOIN normalized n ON n.id = s.normalized_id
        """
    ).fetchall()
    count_in = len(rows)

    lemma_map = key_stage.build_combined_lemma_map(conn)
    cards = stock.load_stock_cards()
    known_by_signature_key, known_by_head_lemma = stock.build_known_signatures(cards, lemma_map)
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
            signature, row["note_type"], denylist, known_by_signature_key, known_by_head_lemma, lemma_map
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
        f"skipped set dumped to {SKIPPED_REVIEW_LOG_PATH} for spot-check (task 4.8)"
    )

    count_out = len(verdicts)
    return count_in, count_out, 0
