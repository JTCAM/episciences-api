"""Shared fixtures: all network traffic is mocked, all token files are
redirected into a temporary directory."""

import base64
import json
import time

import pytest
from episciences.episciences_api import EpisciencesDB

BASE = "https://api.episciences.org"


def make_jwt(exp=None, **claims):
    """Build a syntactically valid (unsigned) JWT."""
    if exp is None:
        exp = int(time.time()) + 3600
    claims.setdefault("sub", "user@example.org")
    claims["exp"] = exp

    def enc(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{enc({'alg': 'HS256'})}.{enc(claims)}.signature"


VALID_TOKEN = make_jwt()
EXPIRED_TOKEN = make_jwt(exp=int(time.time()) - 100)
NEW_TOKEN = make_jwt(sub="refreshed")


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    """Redirect the token storage into a temp file and move away from the
    repository (which contains a legacy token.json)."""
    path = tmp_path / "opencode" / "auth.json"
    monkeypatch.setenv("EPI_TOKEN_FILE", str(path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EPI_USERNAME", raising=False)
    monkeypatch.delenv("EPI_PASSWORD", raising=False)
    monkeypatch.delenv("EPI_JOURNAL", raising=False)
    return path


@pytest.fixture
def db(token_file):
    """A connection that does not authenticate on construction."""
    return EpisciencesDB(auto_authenticate=False, retry_backoff=0)


@pytest.fixture
def authed_db(db, requests_mock):
    """A connection holding a valid token (validated against /api/me)."""
    requests_mock.get(f"{BASE}/api/me", json={"email": "user@example.org"})
    db.token = {"token": VALID_TOKEN, "refresh_token": "refresh-1"}
    assert db.check_authentication()
    return db
