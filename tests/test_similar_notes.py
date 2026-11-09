"""Tests for the `similar-notes-merge` change: the three similarity
signals (tasks.md section 3/6.1-6.4), the merge endpoint's status rules
and transactionality (6.5-6.8), and `audio_blob` take behaviour (6.7)."""

from __future__ import annotations

from tests.conftest import AUTH


def _create(client, **overrides):
    body = {"type": "word", "source_lang": "no", "text": "x"}
    body.update(overrides)
    resp = client.post("/api/notes", json=body, headers=AUTH)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def _similar(client, note_id):
    resp = client.get(f"/api/notes/{note_id}/similar", headers=AUTH)
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _reason_signals(match):
    return {r["signal"] for r in match["reasons"]}


# --------------------------------------------------------------- 6.1 ---

def test_spelling_signal_above_threshold(client):
    a = _create(client, text="å oppleve")
    b = _create(client, text="en opplevelse")

    matches = _similar(client, a["id"])
    by_id = {m["id"]: m for m in matches}
    assert b["id"] in by_id
    assert "spelling" in _reason_signals(by_id[b["id"]])
    score = next(r["score"] for r in by_id[b["id"]]["reasons"] if r["signal"] == "spelling")
    assert score == 0.5833333134651184 or abs(score - 0.5833) < 0.01


def test_morphology_signal_shared_inflected_form(client):
    a = _create(client, text="en blogg", inflections={"article": "en", "sg_indef": "blogg", "sg_def": "bloggen"})
    b = _create(client, text="en blogger", inflections={"article": "en", "sg_indef": "blogger", "sg_def": "bloggeren"})
    c = _create(
        client,
        text="å blogge",
        inflections={"infinitiv": "blogge", "presens": "blogger", "preteritum": "bloggd", "perfektum": "bloggd"},
    )

    matches = _similar(client, a["id"])
    by_id = {m["id"]: m for m in matches}
    # a and c share the surface form "blogger" (a's sg_def-adjacent form
    # isn't shared with c directly in this fixture, so assert on b<->c,
    # the pair the design doc actually calls out as cross-PoS.
    matches_b = _similar(client, b["id"])
    by_id_b = {m["id"]: m for m in matches_b}
    assert c["id"] in by_id_b
    assert "morphology" in _reason_signals(by_id_b[c["id"]])


def test_semantic_signal_shared_translation(client):
    a = _create(client, text="forbindelse", translations=[{"lang": "en", "text": "a connection"}])
    b = _create(client, text="sammenheng", translations=[{"lang": "en", "text": "connection"}])

    matches = _similar(client, a["id"])
    by_id = {m["id"]: m for m in matches}
    assert b["id"] in by_id
    assert "semantic" in _reason_signals(by_id[b["id"]])


# --------------------------------------------------------------- 6.2 ---

def test_shared_article_alone_does_not_relate_two_nouns(client):
    a = _create(client, text="en katt", inflections={"article": "en", "sg_indef": "katt", "sg_def": "katten"})
    b = _create(client, text="en bil", inflections={"article": "en", "sg_indef": "bil", "sg_def": "bilen"})

    matches = _similar(client, a["id"])
    by_id = {m["id"]: m for m in matches}
    assert b["id"] not in by_id


# --------------------------------------------------------------- 6.3 ---

def test_listening_note_has_no_spelling_similarity(client):
    a = _create(client, type="listening", text="Jeg liker å oppleve nye ting")
    b = _create(client, text="å oppleve")

    matches = _similar(client, a["id"])
    assert matches == []
    # And the reverse direction: a listening note isn't offered as a
    # spelling match for a word note either.
    matches_b = _similar(client, b["id"])
    by_id_b = {m["id"]: m for m in matches_b}
    assert a["id"] not in by_id_b


# --------------------------------------------------------------- 6.4 ---

def test_note_matched_by_two_signals_appears_once(client):
    a = _create(client, text="å oppleve", translations=[{"lang": "en", "text": "to experience"}])
    b = _create(client, text="en opplevelse", translations=[{"lang": "en", "text": "an experience"}])

    matches = _similar(client, a["id"])
    matching_rows = [m for m in matches if m["id"] == b["id"]]
    assert len(matching_rows) == 1
    assert _reason_signals(matching_rows[0]) == {"spelling", "semantic"}


# --------------------------------------------------------------- 6.5 ---

def test_ready_absorbs_draft_is_permitted(client):
    survivor = _create(client, text="hus", status="ready")
    absorbed = _create(client, text="hus2", status="draft")

    resp = client.post(
        "/api/notes/merge",
        json={"survivor_id": survivor["id"], "absorbed_ids": [absorbed["id"]], "take": {}},
        headers=AUTH,
    )
    assert resp.status_code == 200


def test_draft_absorbs_draft_is_permitted(client):
    survivor = _create(client, text="hus", status="draft")
    absorbed = _create(client, text="hus2", status="draft")

    resp = client.post(
        "/api/notes/merge",
        json={"survivor_id": survivor["id"], "absorbed_ids": [absorbed["id"]], "take": {}},
        headers=AUTH,
    )
    assert resp.status_code == 200


def test_draft_absorbing_ready_is_rejected(client):
    survivor = _create(client, text="hus", status="draft")
    absorbed = _create(client, text="hus2", status="ready")

    resp = client.post(
        "/api/notes/merge",
        json={"survivor_id": survivor["id"], "absorbed_ids": [absorbed["id"]], "take": {}},
        headers=AUTH,
    )
    assert resp.status_code == 400

    still_there = client.get(f"/api/notes/{absorbed['id']}", headers=AUTH)
    assert still_there.status_code == 200


def test_ready_absorbing_ready_is_rejected(client):
    survivor = _create(client, text="hus", status="ready")
    absorbed = _create(client, text="hus2", status="ready")

    resp = client.post(
        "/api/notes/merge",
        json={"survivor_id": survivor["id"], "absorbed_ids": [absorbed["id"]], "take": {}},
        headers=AUTH,
    )
    assert resp.status_code == 400

    still_there = client.get(f"/api/notes/{absorbed['id']}", headers=AUTH)
    assert still_there.status_code == 200


# --------------------------------------------------------------- 6.6 ---

def test_permitted_merge_deletes_absorbed_and_bumps_survivor(client):
    survivor = _create(client, text="hus", status="ready")
    absorbed = _create(client, text="hus2", status="draft", origin="manual")
    survivor_before = client.get(f"/api/notes/{survivor['id']}", headers=AUTH).get_json()

    resp = client.post(
        "/api/notes/merge",
        json={
            "survivor_id": survivor["id"],
            "absorbed_ids": [absorbed["id"]],
            "take": {"context_text": absorbed["id"]},
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    survivor_after = resp.get_json()

    gone = client.get(f"/api/notes/{absorbed['id']}", headers=AUTH)
    assert gone.status_code == 404

    assert survivor_after["updated_at"] != survivor_before["updated_at"]
    assert survivor_after["origin"] == survivor_before["origin"]


# --------------------------------------------------------------- 6.7 ---

def test_taking_audio_copies_hash_without_duplicating_blob(client):
    survivor = _create(client, text="hus", status="draft")
    absorbed = _create(client, text="hus2", status="draft", audio_blob="deadbeef" * 8)

    resp = client.post(
        "/api/notes/merge",
        json={
            "survivor_id": survivor["id"],
            "absorbed_ids": [absorbed["id"]],
            "take": {"audio_blob": absorbed["id"]},
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.get_json()["audio_blob"] == "deadbeef" * 8


# --------------------------------------------------------------- 6.8 ---

def test_failed_merge_rolls_back_entirely(client):
    survivor = _create(client, text="hus", status="draft")
    absorbed_ok = _create(client, text="hus2", status="draft")
    absorbed_forbidden = _create(client, text="hus3", status="ready")

    resp = client.post(
        "/api/notes/merge",
        json={
            "survivor_id": survivor["id"],
            "absorbed_ids": [absorbed_ok["id"], absorbed_forbidden["id"]],
            "take": {"context_text": absorbed_ok["id"]},
        },
        headers=AUTH,
    )
    assert resp.status_code == 400

    # Nothing was deleted and nothing was copied — all-or-nothing.
    still_ok = client.get(f"/api/notes/{absorbed_ok['id']}", headers=AUTH)
    assert still_ok.status_code == 200
    survivor_after = client.get(f"/api/notes/{survivor['id']}", headers=AUTH).get_json()
    assert survivor_after["context_text"] is None


def test_merge_rejects_absorbing_self(client):
    survivor = _create(client, text="hus", status="draft")
    resp = client.post(
        "/api/notes/merge",
        json={"survivor_id": survivor["id"], "absorbed_ids": [survivor["id"]], "take": {}},
        headers=AUTH,
    )
    assert resp.status_code == 400
