"""operator-settings: defaults-on-read, partial write, and catalogue
reconciliation (tasks 6.1-6.9, backend tests for 6.10). Every test mocks
smia_client.get itself, never a real network call — same convention as
tests/test_enrich.py."""

from __future__ import annotations

import smia_client
from tests.conftest import AUTH


def _mock_catalogue(monkeypatch, catalogue):
    monkeypatch.setattr(smia_client, "get", lambda path, timeout=20.0: (200, catalogue))


def test_reading_before_anything_configured_returns_full_defaults(client, monkeypatch):
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "nst"]})
    resp = client.get("/api/settings", headers=AUTH)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["translation_merge_mode"] == "append"
    assert body["override_prefill"] is True
    assert body["default_target_langs"] == ["en", "de"]
    assert body["providers"]["ipa"]["order"] == ["wikipron", "nst"]
    assert body["providers"]["ipa"]["primary"] == "wikipron"


def test_settings_requires_auth(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 401


def test_partial_write_leaves_other_preferences_at_default(client, monkeypatch):
    _mock_catalogue(monkeypatch, {})
    resp = client.patch(
        "/api/settings", json={"translation_merge_mode": "separate"}, headers=AUTH
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["translation_merge_mode"] == "separate"
    # Untouched preferences remain at their defaults.
    assert body["override_prefill"] is True
    assert body["default_target_langs"] == ["en", "de"]


def test_partial_write_leaves_other_preferences_at_their_stored_values(client, monkeypatch):
    _mock_catalogue(monkeypatch, {})
    client.patch("/api/settings", json={"override_prefill": False}, headers=AUTH)
    resp = client.patch(
        "/api/settings", json={"default_target_langs": ["fr"]}, headers=AUTH
    )
    body = resp.get_json()
    assert body["default_target_langs"] == ["fr"]
    # The earlier write to override_prefill survives this later, unrelated write.
    assert body["override_prefill"] is False


def test_writing_one_kinds_order_does_not_touch_another_kinds(client, monkeypatch):
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "nst"], "tts": ["kaikki_tts", "elevenlabs"]})
    client.patch(
        "/api/settings",
        json={"providers": {"tts": {"order": ["elevenlabs", "kaikki_tts"]}}},
        headers=AUTH,
    )
    resp = client.patch(
        "/api/settings",
        json={"providers": {"ipa": {"order": ["nst", "wikipron"]}}},
        headers=AUTH,
    )
    body = resp.get_json()
    assert body["providers"]["ipa"]["order"] == ["nst", "wikipron"]
    assert body["providers"]["tts"]["order"] == ["elevenlabs", "kaikki_tts"]


def test_unknown_settings_key_is_rejected(client, monkeypatch):
    _mock_catalogue(monkeypatch, {})
    resp = client.patch("/api/settings", json={"bogus": 1}, headers=AUTH)
    assert resp.status_code == 400


def test_invalid_merge_mode_is_rejected(client, monkeypatch):
    _mock_catalogue(monkeypatch, {})
    resp = client.patch("/api/settings", json={"translation_merge_mode": "sideways"}, headers=AUTH)
    assert resp.status_code == 400


def test_unknown_kind_is_rejected(client, monkeypatch):
    _mock_catalogue(monkeypatch, {})
    resp = client.patch(
        "/api/settings", json={"providers": {"notakind": {"order": ["x"]}}}, headers=AUTH
    )
    assert resp.status_code == 400


def test_duplicate_provider_in_order_is_rejected(client, monkeypatch):
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "nst"]})
    resp = client.patch(
        "/api/settings",
        json={"providers": {"ipa": {"order": ["wikipron", "wikipron"]}}},
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_provider_absent_from_catalogue_is_retained_not_refused(client, monkeypatch):
    # D3/3.3: a stored provider the current catalogue doesn't mention is
    # retained, not rejected — the catalogue can change underneath stabbur.
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron"]})
    resp = client.patch(
        "/api/settings",
        json={"providers": {"ipa": {"order": ["wikipron", "ghost_provider"]}}},
        headers=AUTH,
    )
    assert resp.status_code == 200


def test_reordering_changes_the_primary(client, monkeypatch):
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "ipadict", "nst"]})
    resp = client.patch(
        "/api/settings",
        json={"providers": {"ipa": {"order": ["nst", "wikipron", "ipadict"]}}},
        headers=AUTH,
    )
    assert resp.get_json()["providers"]["ipa"]["primary"] == "nst"


def test_disabling_the_first_provider_promotes_the_next(client, monkeypatch):
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "ipadict", "nst"]})
    resp = client.patch(
        "/api/settings",
        json={"providers": {"ipa": {"order": ["wikipron", "ipadict", "nst"], "disabled": ["wikipron"]}}},
        headers=AUTH,
    )
    assert resp.get_json()["providers"]["ipa"]["primary"] == "ipadict"


def test_a_vanished_provider_is_skipped_without_error(client, monkeypatch):
    # Store an order while nst is present.
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "nst"]})
    client.patch(
        "/api/settings", json={"providers": {"ipa": {"order": ["wikipron", "nst"]}}}, headers=AUTH
    )
    # nst vanishes from the catalogue (e.g. its token got unset).
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron"]})
    resp = client.get("/api/settings", headers=AUTH)
    ipa = resp.get_json()["providers"]["ipa"]
    assert ipa["order"] == ["wikipron"]
    assert ipa["primary"] == "wikipron"


def test_a_vanished_provider_resumes_its_stored_position_and_enabled_state_on_return(client, monkeypatch):
    # The reconciliation case most likely to be got subtly wrong (design
    # D3 / Risks) — a disabled provider must come back disabled, at the
    # same position, not treated as newly discovered and re-enabled.
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "nst", "ipadict"]})
    client.patch(
        "/api/settings",
        json={
            "providers": {
                "ipa": {"order": ["wikipron", "nst", "ipadict"], "disabled": ["nst"]}
            }
        },
        headers=AUTH,
    )

    # nst vanishes.
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "ipadict"]})
    vanished = client.get("/api/settings", headers=AUTH).get_json()["providers"]["ipa"]
    assert vanished["order"] == ["wikipron", "ipadict"]

    # nst reappears.
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "nst", "ipadict"]})
    returned = client.get("/api/settings", headers=AUTH).get_json()["providers"]["ipa"]
    assert returned["order"] == ["wikipron", "nst", "ipadict"]
    assert "nst" in returned["disabled"]
    assert returned["primary"] == "wikipron"


def test_a_new_provider_is_appended_enabled_and_is_not_primary(client, monkeypatch):
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron"]})
    client.patch(
        "/api/settings", json={"providers": {"ipa": {"order": ["wikipron"]}}}, headers=AUTH
    )

    # kaikki_ipa is a brand-new provider in the catalogue.
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron", "kaikki_ipa"]})
    resp = client.get("/api/settings", headers=AUTH)
    ipa = resp.get_json()["providers"]["ipa"]
    assert ipa["order"] == ["wikipron", "kaikki_ipa"]
    assert "kaikki_ipa" not in ipa["disabled"]
    assert ipa["primary"] == "wikipron"


def test_every_stored_provider_vanished_still_resolves_a_primary_from_the_catalogue(client, monkeypatch):
    _mock_catalogue(monkeypatch, {"ipa": ["wikipron"]})
    client.patch(
        "/api/settings", json={"providers": {"ipa": {"order": ["wikipron"]}}}, headers=AUTH
    )

    _mock_catalogue(monkeypatch, {"ipa": ["ipadict", "nst"]})
    resp = client.get("/api/settings", headers=AUTH)
    ipa = resp.get_json()["providers"]["ipa"]
    assert ipa["order"] == ["ipadict", "nst"]
    assert ipa["primary"] == "ipadict"


def test_smia_unreachable_degrades_to_stored_order_rather_than_failing(client, monkeypatch):
    def fake_get(path, timeout=20.0):
        raise smia_client.SmiaUnavailableError("connection refused")

    monkeypatch.setattr(smia_client, "get", fake_get)
    resp = client.get("/api/settings", headers=AUTH)
    assert resp.status_code == 200
