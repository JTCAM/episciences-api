"""Authentication flow tests: login, refresh, token persistence, precedence."""

import json

import pytest
from episciences.episciences_api import (
    AuthenticationError,
    EpisciencesDB,
    TokenStorage,
)

from .conftest import BASE, EXPIRED_TOKEN, NEW_TOKEN, VALID_TOKEN


def test_fetch_token_persists_to_auth_json(db, requests_mock, token_file):
    requests_mock.post(
        f"{BASE}/api/login",
        json={"token": VALID_TOKEN, "refresh_token": "refresh-1"},
    )
    db.fetch_token("user", "pass")

    assert db.token["token"] == VALID_TOKEN
    assert db.token["refresh_token"] == "refresh-1"

    data = json.loads(token_file.read_text())
    assert data["episciences"]["access"] == VALID_TOKEN
    assert data["episciences"]["refresh"] == "refresh-1"


def test_fetch_token_sends_credentials_and_journal(db, requests_mock):
    m = requests_mock.post(
        f"{BASE}/api/login", json={"token": VALID_TOKEN, "refresh_token": "r"}
    )
    db.fetch_token("user", "pass")
    sent = m.last_request.json()
    assert sent == {"username": "user", "password": "pass", "code": "jtcam"}


def test_fetch_token_bad_credentials(db, requests_mock, token_file):
    requests_mock.post(
        f"{BASE}/api/login", status_code=401, json={"code": 401, "message": "Invalid credentials."}
    )
    with pytest.raises(AuthenticationError):
        db.fetch_token("user", "wrong")
    assert not token_file.exists()


def test_fetch_token_missing_credentials_raises(db):
    with pytest.raises(AuthenticationError):
        db.fetch_token(None, None)


def test_fetch_token_missing_credentials_interactive(db, monkeypatch):
    answers = iter(["cli-user", "cli-pass"])
    db.interactive = True
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    monkeypatch.setattr("getpass.getpass", lambda *a: next(answers))

    def fake_request(self, method, path, **kwargs):
        return {"token": VALID_TOKEN, "refresh_token": "r"}

    monkeypatch.setattr(EpisciencesDB, "_request", fake_request)
    token = db.fetch_token()
    assert token["token"] == VALID_TOKEN


def test_refresh_token_success(db, requests_mock, token_file):
    db.token = {"token": EXPIRED_TOKEN, "refresh_token": "refresh-old"}
    requests_mock.post(
        f"{BASE}/api/token/refresh",
        json={"token": NEW_TOKEN, "refresh_token": "refresh-new"},
    )
    assert db.refresh_token() is True
    assert db.token["token"] == NEW_TOKEN
    assert db.token["refresh_token"] == "refresh-new"
    # the rotated pair is persisted
    data = json.loads(token_file.read_text())
    assert data["episciences"]["access"] == NEW_TOKEN
    assert data["episciences"]["refresh"] == "refresh-new"


def test_refresh_failure_does_not_corrupt_storage(db, requests_mock, token_file):
    storage = TokenStorage()
    storage.save(VALID_TOKEN, "good-refresh")

    db.token = {"token": EXPIRED_TOKEN, "refresh_token": "revoked-refresh"}
    requests_mock.post(
        f"{BASE}/api/token/refresh",
        status_code=401,
        json={"code": 401, "message": "Invalid JWT Refresh Token"},
    )
    assert db.refresh_token() is False
    # the previously stored token is untouched
    assert storage.load()["token"] == VALID_TOKEN


def test_refresh_without_refresh_token(db):
    db.token = {"token": VALID_TOKEN}
    assert db.refresh_token() is False


def test_authenticate_with_provided_token(requests_mock, token_file):
    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    conn = EpisciencesDB(token=VALID_TOKEN, retry_backoff=0)
    assert conn.token["token"] == VALID_TOKEN


def test_authenticate_rejects_invalid_provided_token_without_fallback(
    requests_mock, token_file
):
    requests_mock.get(f"{BASE}/api/me", status_code=401, json={"code": 401})
    with pytest.raises(AuthenticationError):
        EpisciencesDB(token=EXPIRED_TOKEN, retry_backoff=0)


def test_authenticate_uses_stored_then_refreshes(requests_mock, token_file):
    TokenStorage().save(EXPIRED_TOKEN, "refresh-1")
    requests_mock.post(
        f"{BASE}/api/token/refresh",
        json={"token": NEW_TOKEN, "refresh_token": "refresh-2"},
    )
    requests_mock.get(
        f"{BASE}/api/me",
        [
            {"status_code": 401, "json": {"code": 401, "message": "Expired JWT Token"}},
            {"json": {"email": "u@example.org"}},
        ],
    )
    conn = EpisciencesDB(retry_backoff=0)
    assert conn.token["token"] == NEW_TOKEN


def test_authenticate_falls_back_to_env_credentials(requests_mock, token_file, monkeypatch):
    monkeypatch.setenv("EPI_USERNAME", "ci-user")
    monkeypatch.setenv("EPI_PASSWORD", "ci-pass")
    TokenStorage().save(EXPIRED_TOKEN, "revoked-refresh")
    requests_mock.post(
        f"{BASE}/api/token/refresh",
        status_code=401,
        json={"code": 401, "message": "Invalid JWT Refresh Token"},
    )
    login = requests_mock.post(
        f"{BASE}/api/login",
        json={"token": NEW_TOKEN, "refresh_token": "refresh-2"},
    )
    requests_mock.get(
        f"{BASE}/api/me",
        [
            {"status_code": 401, "json": {"code": 401, "message": "Expired JWT Token"}},
            {"json": {"email": "u@example.org"}},
        ],
    )
    conn = EpisciencesDB(retry_backoff=0)
    assert conn.token["token"] == NEW_TOKEN
    assert login.last_request.json()["username"] == "ci-user"


def test_authenticate_no_credentials_raises(token_file):
    with pytest.raises(AuthenticationError):
        EpisciencesDB(retry_backoff=0)


def test_explicit_credentials_take_precedence_over_storage(requests_mock, token_file):
    TokenStorage().save(EXPIRED_TOKEN, "stale")
    login = requests_mock.post(
        f"{BASE}/api/login",
        json={"token": NEW_TOKEN, "refresh_token": "r"},
    )
    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    conn = EpisciencesDB(username="user", password="pass", retry_backoff=0)
    assert login.called
    assert conn.token["token"] == NEW_TOKEN


def test_expired_access_token_is_refreshed_on_request(
    requests_mock, token_file, db
):
    db.token = {"token": EXPIRED_TOKEN, "refresh_token": "refresh-1"}
    requests_mock.post(
        f"{BASE}/api/token/refresh",
        json={"token": NEW_TOKEN, "refresh_token": "refresh-2"},
    )
    # plain requests do not refresh: check_authentication just fails
    requests_mock.get(f"{BASE}/api/me", status_code=401, json={"code": 401})
    assert db.check_authentication() is False
    # ...but an authenticated GET refreshes and retries transparently
    papers = requests_mock.get(
        f"{BASE}/api/papers/",
        [
            {"status_code": 401, "json": {"code": 401, "message": "Expired JWT Token"}},
            {"json": {"hydra:member": [], "hydra:totalItems": 0}},
        ],
    )
    assert db.list_papers() == []
    assert papers.call_count == 2  # first 401, then success after refresh
    assert db.token["token"] == NEW_TOKEN
