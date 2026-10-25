"""Shared fixtures: a clean notes/grammar_rule table per test, plus a Flask
test client with auth configured."""

from __future__ import annotations

import shutil

import pytest

from db.models import GrammarRule, Note
from db.session import get_sessionmaker


@pytest.fixture(autouse=True)
def clean_db():
    Session = get_sessionmaker()
    with Session() as db:
        db.query(Note).delete()
        db.query(GrammarRule).delete()
        db.commit()
    yield


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("STABBUR_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("STABBUR_BLOB_DIR", str(tmp_path / "blobs"))
    import blob_storage

    monkeypatch.setattr(blob_storage, "BLOB_DIR", str(tmp_path / "blobs"))

    import app as app_module

    yield app_module.app.test_client()

    shutil.rmtree(tmp_path / "blobs", ignore_errors=True)


AUTH = {"Authorization": "Bearer test-token"}
