import os
from pathlib import Path

TEST_DB = "/tmp/docmind-test.sqlite3"
TEST_STORAGE = "/tmp/docmind-test-storage"
for path in [TEST_DB]:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_LOCAL_DIR"] = TEST_STORAGE
os.environ["APP_SECRET"] = "test-secret-at-least-long-enough"
os.environ["AI_MODE"] = "mock"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from app.db import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def register(client: TestClient, email: str = "owner@example.com") -> dict:
    response = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "correct-horse-battery-staple",
        "display_name": "Owner",
        "locale": "en",
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def auth(client):
    data = register(client)
    return {"Authorization": f"Bearer {data['access_token']}"}, data
