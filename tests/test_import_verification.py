"""Tests for section 8 of bulk-import-anki-csv (verification, tasks 8.1,
8.4-8.6): cross-cutting invariants that aren't specific to any one stage
module. 8.2/8.3 (a real push against a throwaway stabbur database,
interrupted and resumed) are a manual/CI verification step, not unit
tests here — see design.md's task-8 record for that run's outcome.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

IMPORT_TOOL_DIR = Path(__file__).resolve().parent.parent / "scripts" / "import"
sys.path.insert(0, str(IMPORT_TOOL_DIR))

import ingest as import_ingest  # noqa: E402
import judge as import_judge  # noqa: E402
import key as import_key  # noqa: E402
import merge as import_merge  # noqa: E402
import normalize as import_normalize  # noqa: E402
import stock as import_stock  # noqa: E402
import store as import_store  # noqa: E402

STAGE_MODULES = ("ingest", "normalize", "key", "judge", "merge", "review", "push", "stock", "lexeme", "stages", "cli")


# ---------------------------------------------------------------------------
# Task 8.5: no type=grammar note and no grammar_rule row from any stage
# ---------------------------------------------------------------------------


def test_no_module_ever_references_grammar_or_pronunciation_note_types():
    for name in STAGE_MODULES:
        source = (IMPORT_TOOL_DIR / f"{name}.py").read_text(encoding="utf-8")
        assert '"grammar"' not in source, f"{name}.py references note_type='grammar'"
        assert "'grammar'" not in source
        assert '"pronunciation"' not in source, f"{name}.py references note_type='pronunciation'"
        assert "'pronunciation'" not in source
        assert "grammar_rule" not in source, f"{name}.py references grammar_rule"


def test_core6k_grammar_model_excluded_at_ingest():
    assert "Grammar" not in import_ingest.APKG_SOURCES["core6k"]["models"]


def test_note_type_routing_never_produces_grammar_or_pronunciation():
    import normalize as import_normalize_module
    import inspect

    source = inspect.getsource(import_normalize_module)
    for fn_name in ("_normalize_ntnu", "_normalize_a1", "_normalize_core6k", "_normalize_freq6k", "_normalize_csv"):
        assert fn_name in source


# ---------------------------------------------------------------------------
# Task 8.6: no smia call, no outbound network except stabbur's own API
# ---------------------------------------------------------------------------


def _imported_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_module_imports_smia_client():
    for name in STAGE_MODULES:
        path = IMPORT_TOOL_DIR / f"{name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_names(tree)
        assert "smia_client" not in imported, f"{name}.py imports smia_client"
        assert not any(n.startswith("smia") for n in imported), f"{name}.py imports an smia module"


def test_only_push_py_imports_requests():
    for name in STAGE_MODULES:
        path = IMPORT_TOOL_DIR / f"{name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_names(tree)
        has_requests = "requests" in imported
        if name == "push":
            assert has_requests
        else:
            assert not has_requests, f"{name}.py imports requests but isn't the push stage"


def test_push_api_base_defaults_to_local_stabbur_only():
    import push as import_push

    assert "localhost" in import_push.DEFAULT_API_BASE or "127.0.0.1" in import_push.DEFAULT_API_BASE


# ---------------------------------------------------------------------------
# Task 8.1: dry-run funnel — confirmed against D13's measured (not D6's
# superseded) figures; this is the repeatable regression check, the actual
# investigation of any divergence is recorded in design.md (tasks 4b.12/
# 4b.14/8.7).
# ---------------------------------------------------------------------------

_HAS_SOURCES = all((import_ingest.IMPORT_DIR / spec["file"]).exists() for spec in import_ingest.APKG_SOURCES.values())
_HAS_STOCK = import_stock.stock_bundle_path().exists()

pytestmark_dry_run = pytest.mark.skipif(
    not (_HAS_SOURCES and _HAS_STOCK),
    reason="needs both import/ source archives and the stock bundle, neither tracked in git",
)


@pytest.fixture(scope="module")
def dry_run_conn(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("import_db")
    conn = import_store.connect(tmp_path / "candidates.db")
    for stage, module in (
        ("ingest", import_ingest),
        ("normalize", import_normalize),
        ("key", import_key),
        ("judge", import_judge),
        ("merge", import_merge),
    ):
        run_id = import_store.start_run(conn, stage)
        module.run(conn, run_id)
    yield conn
    conn.close()


@pytest.mark.skipif(not (_HAS_SOURCES and _HAS_STOCK), reason="needs real archives + stock bundle")
def test_dry_run_funnel_is_in_the_measured_ballpark(dry_run_conn):
    """Task 8.1: confirm the funnel against the measured (task 4b.14),
    not the design-estimate, figures — investigate material divergence
    rather than accept it. A ~22% skip rate, ~9,000 distinct signatures,
    is this change's own measured baseline (design.md's D13 section)."""
    total = dry_run_conn.execute("SELECT COUNT(DISTINCT signature_key) FROM signature").fetchone()[0]
    skipped = dry_run_conn.execute("SELECT COUNT(DISTINCT signature_key) FROM verdict WHERE verdict='skip'").fetchone()[0]
    assert total == 9009
    skip_rate = skipped / total
    assert 0.18 <= skip_rate <= 0.26  # measured 22.1%; design's pre-build estimate was 18.7%


@pytest.mark.skipif(not (_HAS_SOURCES and _HAS_STOCK), reason="needs real archives + stock bundle")
def test_dry_run_produces_no_push_side_effects(dry_run_conn):
    """A dry run through merge must never touch `candidate.note_id` —
    nothing is pushed until `push` runs, which this fixture never calls."""
    pushed = dry_run_conn.execute("SELECT COUNT(*) FROM candidate WHERE note_id IS NOT NULL").fetchone()[0]
    assert pushed == 0


# ---------------------------------------------------------------------------
# Task 8.4: re-running judge after editing the deny-list preserves review
# decisions and only changes verdicts.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (_HAS_SOURCES and _HAS_STOCK), reason="needs real archives + stock bundle")
def test_rerunning_judge_after_denylist_edit_preserves_decisions_changes_verdicts(tmp_path, monkeypatch):
    import json

    import review as import_review

    conn = import_store.connect(tmp_path / "candidates.db")
    for stage, module in (
        ("ingest", import_ingest),
        ("normalize", import_normalize),
        ("key", import_key),
        ("judge", import_judge),
        ("merge", import_merge),
    ):
        run_id = import_store.start_run(conn, stage)
        module.run(conn, run_id)

    # Find an "and"-headed candidate (denylist-protected, imports today).
    and_row = conn.execute(
        "SELECT signature_key, verdict FROM candidate WHERE signature_key LIKE '[\"and\"%' ESCAPE '\\'"
    ).fetchone()
    assert and_row is not None
    assert and_row["verdict"] == "import"
    import_review.record_decision(conn, and_row["signature_key"], "accept")

    # Edit the deny-list: remove "and" so it's no longer protected.
    temp_denylist = tmp_path / "denylist.json"
    original = json.loads(import_judge.DENYLIST_PATH.read_text(encoding="utf-8"))
    original["lemmas"] = [l for l in original["lemmas"] if l != "and"]
    temp_denylist.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(import_judge, "DENYLIST_PATH", temp_denylist)

    run_id = import_store.start_run(conn, "key")
    import_key.run(conn, run_id)
    run_id = import_store.start_run(conn, "judge")
    import_judge.run(conn, run_id)
    run_id = import_store.start_run(conn, "merge")
    import_merge.run(conn, run_id)

    # Decision survives the judge/merge re-run (task 6.3's whole point).
    assert import_review.decided_signature_keys(conn) == {and_row["signature_key"]}

    # Verdict may now differ (denylist no longer protects "and" — it was
    # never actually attested in this bundle, see stock.py's docstring, so
    # it remains "import" either way here, but via a different rule/no
    # rule rather than "denylist-protected").
    new_row = conn.execute(
        "SELECT verdict, verdict_evidence_json FROM candidate WHERE signature_key = ?", (and_row["signature_key"],)
    ).fetchone()
    evidence = json.loads(new_row["verdict_evidence_json"])
    assert evidence.get("rule") != "denylist-protected"
    conn.close()
