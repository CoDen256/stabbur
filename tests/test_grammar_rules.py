"""Task 4.5 — grammar rule CRUD: single-rule GET/PATCH/DELETE, delete
blocked while referenced with an accurate count, list sort/search."""

from __future__ import annotations

from tests.conftest import AUTH


def _create_rule(client, title="Perfektum of strong verbs", html="<p>x</p>"):
    resp = client.post("/api/grammar_rules", json={"title": title, "html": html}, headers=AUTH)
    assert resp.status_code == 201
    return resp.get_json()


def test_get_single_rule(client):
    rule = _create_rule(client)
    resp = client.get(f"/api/grammar_rules/{rule['id']}", headers=AUTH)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == rule["title"]
    assert resp.get_json()["usage_count"] == 0


def test_get_unknown_rule_is_404(client):
    resp = client.get("/api/grammar_rules/999999", headers=AUTH)
    assert resp.status_code == 404


def test_patch_edits_title_and_html(client):
    rule = _create_rule(client)
    resp = client.patch(
        f"/api/grammar_rules/{rule['id']}", json={"title": "New title", "html": "<p>new</p>"}, headers=AUTH
    )
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "New title"
    assert resp.get_json()["html"] == "<p>new</p>"


def test_delete_blocked_while_referenced_reports_accurate_count(client):
    rule = _create_rule(client)
    for _ in range(3):
        resp = client.post(
            "/api/notes",
            json={"type": "grammar", "source_lang": "no", "text": "x", "grammar_rule_id": rule["id"]},
            headers=AUTH,
        )
        assert resp.status_code == 201

    resp = client.delete(f"/api/grammar_rules/{rule['id']}", headers=AUTH)
    assert resp.status_code == 409
    assert resp.get_json()["reference_count"] == 3


def test_delete_succeeds_when_unused(client):
    rule = _create_rule(client)
    resp = client.delete(f"/api/grammar_rules/{rule['id']}", headers=AUTH)
    assert resp.status_code == 204

    assert client.get(f"/api/grammar_rules/{rule['id']}", headers=AUTH).status_code == 404


def test_list_sorts_by_usage_count(client):
    popular = _create_rule(client, title="Popular")
    unpopular = _create_rule(client, title="Unpopular")
    client.post(
        "/api/notes",
        json={"type": "grammar", "source_lang": "no", "text": "x", "grammar_rule_id": popular["id"]},
        headers=AUTH,
    )

    resp = client.get("/api/grammar_rules?sort=usage_desc", headers=AUTH)
    titles = [r["title"] for r in resp.get_json()]
    assert titles.index("Popular") < titles.index("Unpopular")


def test_list_search_by_title(client):
    _create_rule(client, title="Perfektum of strong verbs")
    _create_rule(client, title="Reflexive pronouns")

    resp = client.get("/api/grammar_rules?q=reflexive", headers=AUTH)
    titles = {r["title"] for r in resp.get_json()}
    assert titles == {"Reflexive pronouns"}
