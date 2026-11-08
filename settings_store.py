"""
settings_store.py — operator-settings defaults and catalogue reconciliation
(operator-settings design D1-D4). routes/settings.py is the only caller;
this module holds the logic so it's unit-testable without a Flask request.

Defaults live here, in code, not in the database (D2) — reading settings
before anything has ever been written returns these, so no caller ever has
to branch on "unconfigured" vs. "configured".
"""

from __future__ import annotations

from db.models import Settings

TRANSLATION_MERGE_MODES = ("append", "separate")

DEFAULT_TRANSLATION_MERGE_MODE = "append"
DEFAULT_OVERRIDE_PREFILL = True
DEFAULT_TARGET_LANGS = ("en", "de")


def _row(db) -> Settings | None:
    return db.get(Settings, 1)


def read_scalars(db) -> dict:
    """Stored scalar preferences with defaults applied (D2) — no catalogue
    involved, since these aren't provider-ordering preferences."""
    row = _row(db)
    return {
        "translation_merge_mode": (row.translation_merge_mode if row else None) or DEFAULT_TRANSLATION_MERGE_MODE,
        "override_prefill": DEFAULT_OVERRIDE_PREFILL if row is None or row.override_prefill is None else row.override_prefill,
        "default_target_langs": (row.default_target_langs if row else None) or list(DEFAULT_TARGET_LANGS),
    }


def resolve_kind_order(stored: dict, catalogue_providers: list[str]) -> dict:
    """design D3: known providers in stored order first (a vanished one is
    skipped, not an error, with its position and enabled state retained in
    storage so it resumes its place if it returns); a catalogue provider
    absent from the stored order is appended at the end, enabled. The
    primary is derived as the first enabled provider in the effective
    order — never stored separately (D3/2.4)."""
    stored_order = stored.get("order") or []
    stored_disabled = set(stored.get("disabled") or [])
    catalogue_set = set(catalogue_providers or [])

    effective = [p for p in stored_order if p in catalogue_set]
    effective += [p for p in (catalogue_providers or []) if p not in stored_order]

    disabled = sorted(stored_disabled & set(effective))
    primary = next((p for p in effective if p not in stored_disabled), None)

    return {"order": effective, "disabled": disabled, "primary": primary}


def resolve_providers(db, catalogue: dict, kinds: tuple[str, ...]) -> dict:
    """Reconciles every kind stabbur proxies against smia's live catalogue
    (D3 — "every time the ordering is used"; reading settings counts). A
    kind absent from `catalogue` (e.g. smia unreachable) reconciles against
    an empty catalogue, which still resolves cleanly via resolve_kind_order
    — it just means nothing new gets appended this time."""
    row = _row(db)
    provider_prefs = (row.provider_prefs if row else None) or {}
    return {
        kind: resolve_kind_order(provider_prefs.get(kind, {}), catalogue.get(kind, []))
        for kind in kinds
    }


def write(db, updates: dict, kinds: tuple[str, ...]) -> None:
    """Partial update (3.2): only the keys present in `updates` are
    touched; everything else — including other kinds' provider ordering —
    is left at its stored or default value (6.2)."""
    row = _row(db)
    if row is None:
        row = Settings(id=1)
        db.add(row)

    if "translation_merge_mode" in updates:
        row.translation_merge_mode = updates["translation_merge_mode"]
    if "override_prefill" in updates:
        row.override_prefill = updates["override_prefill"]
    if "default_target_langs" in updates:
        row.default_target_langs = updates["default_target_langs"]

    if "providers" in updates:
        # Reassigned as a new dict (not mutated in place) so SQLAlchemy's
        # plain (non-Mutable) JSONB column tracks the change as dirty.
        prefs = dict(row.provider_prefs or {})
        for kind, kind_update in updates["providers"].items():
            if kind not in kinds:
                continue
            existing = dict(prefs.get(kind, {}))
            if "order" in kind_update:
                existing["order"] = kind_update["order"]
            if "disabled" in kind_update:
                existing["disabled"] = kind_update["disabled"]
            prefs[kind] = existing
        row.provider_prefs = prefs

    db.flush()
