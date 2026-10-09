"""Shared fixtures: every test gets an isolated SQLite DB and storage folder in tmp_path.

Note: TestClient runs BackgroundTasks before returning the response, so by the time
`client.post(...)` returns, the job has already been processed. This keeps tests deterministic.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.dependencies import get_session_factory, get_storage
from app.main import app
from app.services.storage import LocalFileStorage


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def storage(tmp_path):
    return LocalFileStorage(tmp_path / "certificates")


@pytest.fixture
def client(session_factory, storage):
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()
