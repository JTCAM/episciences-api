"""Tests for TokenStorage: the OpenCode auth.json integration."""

import json
import os
import stat
import time

import pytest
from episciences.episciences_api import TokenStorage, jwt_expiry

from .conftest import VALID_TOKEN, make_jwt


def test_default_path_from_env(token_file):
    assert TokenStorage().path == token_file


def test_default_path_xdg(tmp_path, monkeypatch):
    monkeypatch.delenv("EPI_TOKEN_FILE", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert TokenStorage().path == tmp_path / "opencode" / "auth.json"


def test_default_path_home(tmp_path, monkeypatch):
    monkeypatch.delenv("EPI_TOKEN_FILE", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert TokenStorage().path == tmp_path / ".local" / "share" / "opencode" / "auth.json"


def test_save_load_roundtrip(token_file):
    storage = TokenStorage()
    storage.save(VALID_TOKEN, "refresh-xyz", journal="jtcam")
    stored = storage.load()
    assert stored["token"] == VALID_TOKEN
    assert stored["refresh_token"] == "refresh-xyz"


def test_saved_entry_matches_opencode_shape(token_file):
    storage = TokenStorage()
    storage.save(VALID_TOKEN, "refresh-xyz", journal="jtcam")
    data = json.loads(token_file.read_text())
    entry = data["episciences"]
    assert entry["type"] == "oauth"
    assert entry["access"] == VALID_TOKEN
    assert entry["refresh"] == "refresh-xyz"
    assert entry["journal"] == "jtcam"
    assert entry["expires"] == pytest.approx(jwt_expiry(VALID_TOKEN) * 1000, rel=1e-3)


def test_save_preserves_other_entries(token_file):
    other = {"anthropic": {"type": "api", "key": "sk-..."}}
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps(other))

    storage = TokenStorage()
    storage.save(VALID_TOKEN, None)

    data = json.loads(token_file.read_text())
    assert data["anthropic"] == other["anthropic"]
    assert "episciences" in data


def test_save_creates_file_with_secure_permissions(token_file):
    storage = TokenStorage()
    storage.save(VALID_TOKEN, None)
    mode = stat.S_IMODE(os.stat(token_file).st_mode)
    assert mode == 0o600


def test_save_rejects_empty_token(token_file):
    with pytest.raises(ValueError):
        TokenStorage().save("")


def test_clear_removes_only_our_entry(token_file):
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps({"other": {"a": 1}}))
    storage = TokenStorage()
    storage.save(VALID_TOKEN, None)
    storage.clear()
    data = json.loads(token_file.read_text())
    assert "episciences" not in data
    assert data["other"] == {"a": 1}


def test_load_missing_file(token_file):
    assert TokenStorage().load() is None


def test_load_corrupt_file(token_file):
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text("{not json")
    assert TokenStorage().load() is None


def test_legacy_token_json_fallback(token_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "token.json").write_text(
        json.dumps({"token": VALID_TOKEN, "refresh_token": "legacy-refresh"})
    )
    stored = TokenStorage().load()
    assert stored["token"] == VALID_TOKEN
    assert stored["refresh_token"] == "legacy-refresh"


def test_status(token_file):
    storage = TokenStorage()
    assert storage.status() == {"stored": False}
    storage.save(make_jwt(exp=int(time.time()) + 500), "r")
    status = storage.status()
    assert status["stored"] is True
    assert status["expired"] is False
    assert status["has_refresh_token"] is True
    assert status["expires_in_seconds"] > 400


def test_atomic_write_leaves_no_tmp_files(token_file):
    storage = TokenStorage()
    storage.save(VALID_TOKEN, None)
    storage.save(make_jwt(), None)  # overwrite
    leftovers = [p for p in token_file.parent.iterdir() if p.name != "auth.json"]
    assert leftovers == []
