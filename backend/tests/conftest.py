"""
conftest.py — Shared pytest fixtures for CityShield tests.

Sets up an in-memory SQLite test database and a FastAPI TestClient
with the Kafka consumer startup task mocked out so tests run
without a live Kafka broker.
"""
import sys
import os
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend dir to path so imports work from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models_db
from database import Base


from sqlalchemy.pool import StaticPool

# ── In-memory SQLite for tests ──────────────────────────────────────────────
TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Return a clean session for each test, rolled back after."""
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()
    yield session
    session.rollback()
    session.close()


# ── FastAPI TestClient (Kafka consumer mocked out) ───────────────────────────
@pytest.fixture(scope="module")
def client(test_engine):
    """
    Creates a TestClient for the FastAPI app.
    - Overrides the DB to use the in-memory test database.
    - Patches 'consume_kafka' so tests don't need a live Kafka broker.
    """
    from database import SessionLocal
    from sqlalchemy.orm import sessionmaker

    TestingSessionLocal = sessionmaker(bind=test_engine)

    # Patch consume_kafka to be a no-op coroutine
    with patch("main.consume_kafka", new_callable=AsyncMock):
        import main as app_module
        # Override DB session factory used by REST endpoints
        app_module.SessionLocal = TestingSessionLocal  # type: ignore

        with TestClient(app_module.app) as c:
            yield c
