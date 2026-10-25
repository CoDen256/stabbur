"""Task 1.2 — GET /api/notes/authoring: every status is visible here, and
the public read API never gains a side-channel for drafts (asserted
together, per design.md D-S1)."""

from __future__ import annotations

from tests.conftest import AUTH


def _create(client, **overrides):
    payload = {"type": "word", "source_lang": "no", "text": "hus"}
    payload.update(overrides)
    resp = client.post("/api/notes", json=payload, headers=AUTH)
    assert resp.status_code == 201
    return resp.get_json()


def test_draft_appears_in_authoring_but_never_in_public_read_api(client):
    draft = _create(client, text="barnevogn", status="draft")

    authoring = client.get("/api/notes/authoring?status=draft", headers=AUTH)
    assert draft["id"] in [n["id"] for n in authoring.get_json()]

    public = client.get("/api/notes?source_lang=no", headers=AUTH)
    assert draft["id"] not in [n["id"] for n in public.get_json()]


def test_filters_by_status_type_pos(client):
    _create(client, text="hus", pos="substantiv", status="ready")
    _create(client, text="løpe", type="word", pos="verb", status="draft")
    _create(client, text="i mellomtiden", type="expression", status="ready")

    resp = client.get("/api/notes/authoring?status=ready&type=word&pos=substantiv", headers=AUTH)
    texts = {n["text"] for n in resp.get_json()}
    assert texts == {"hus"}


def test_search_matches_text_lemma_and_translations(client):
    _create(client, text="hus", lemma="hus", translations=[{"lang": "en", "text": "house"}])
    _create(client, text="bil", lemma="bil", translations=[{"lang": "en", "text": "car"}])

    resp = client.get("/api/notes/authoring?q=house", headers=AUTH)
    assert {n["text"] for n in resp.get_json()} == {"hus"}

    resp = client.get("/api/notes/authoring?q=bil", headers=AUTH)
    assert {n["text"] for n in resp.get_json()} == {"bil"}


def test_sort_text_asc(client):
    _create(client, text="zebra")
    _create(client, text="apekatt")

    resp = client.get("/api/notes/authoring?sort=text_asc", headers=AUTH)
    texts = [n["text"] for n in resp.get_json()]
    assert texts.index("apekatt") < texts.index("zebra")


def test_filters_by_grammar_rule_id(client):
    rule = client.post("/api/grammar_rules", json={"title": "T", "html": "<p>x</p>"}, headers=AUTH).get_json()
    note = _create(client, type="grammar", grammar_rule_id=rule["id"])
    _create(client, text="unrelated")

    resp = client.get(f"/api/notes/authoring?grammar_rule_id={rule['id']}", headers=AUTH)
    ids = [n["id"] for n in resp.get_json()]
    assert ids == [note["id"]]


def test_tombstoned_notes_excluded_from_authoring_list(client):
    note = _create(client, status="ready")
    client.delete(f"/api/notes/{note['id']}", headers=AUTH)

    resp = client.get("/api/notes/authoring", headers=AUTH)
    assert note["id"] not in [n["id"] for n in resp.get_json()]


def test_invalid_status_type_sort_are_rejected(client):
    assert client.get("/api/notes/authoring?status=bogus", headers=AUTH).status_code == 400
    assert client.get("/api/notes/authoring?type=bogus", headers=AUTH).status_code == 400
    assert client.get("/api/notes/authoring?sort=bogus", headers=AUTH).status_code == 400
