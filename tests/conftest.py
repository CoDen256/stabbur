"""Shared fixtures: a clean notes/grammar_rule table per test, plus a Flask
test client with auth configured.

`DATABASE_URL` is resolved and pinned to a dedicated `_test`-suffixed
database *before* anything else in the test session imports `db.session` —
that module binds `DATABASE_URL` to a module-level constant at import time,
so this has to happen first. Without this, `clean_db` below (which must
stay autouse — every test needs a blank slate) would truncate `notes`/
`grammar_rule` in whatever database `DATABASE_URL` already happens to
resolve to, which defaults to the same local dev Postgres `/ui` points at.
That's exactly what happened before this guard existed: running the suite
with a dev `DATABASE_URL` still exported in the shell silently wiped real
hand-authored notes."""

from __future__ import annotations

import os

_DEV_DATABASE_URL = "postgresql+psycopg2://stabbur:stabbur@localhost:5434/stabbur"
_TEST_DATABASE_URL = "postgresql+psycopg2://stabbur:stabbur@localhost:5434/stabbur_test"

_resolved = os.environ.get("DATABASE_URL", _TEST_DATABASE_URL)
if _resolved == _DEV_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is set to the real dev database "
        f"({_DEV_DATABASE_URL}) — tests/conftest.py's clean_db fixture "
        "truncates notes/grammar_rule before every test and would wipe it. "
        "Unset DATABASE_URL (tests default to stabbur_test) or point it at "
        "a dedicated test database."
    )
os.environ["DATABASE_URL"] = _resolved

import shutil  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from db.models import Base, GrammarRule, Note  # noqa: E402
from db.session import get_engine, get_sessionmaker  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_database():
    """Create the `_test` database and its tables if they don't exist yet —
    the test suite should work against a bare `docker compose up postgres`
    with no manual setup step."""
    url = make_url(os.environ["DATABASE_URL"])
    db_name = url.database
    maintenance_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with maintenance_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        maintenance_engine.dispose()

    Base.metadata.create_all(get_engine())


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
