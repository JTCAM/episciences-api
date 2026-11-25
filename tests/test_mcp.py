"""Tests for the MCP server tools (called as plain functions)."""

import json

import pytest
from episciences import mcp_server as srv

from .conftest import BASE, NEW_TOKEN, VALID_TOKEN


@pytest.fixture
def stored_token(token_file):
    """A valid token saved in the token storage, as after a login."""
    from episciences.episciences_api import TokenStorage

    TokenStorage().save(VALID_TOKEN, "r1")
    return VALID_TOKEN


def parse(result):
    return json.loads(result)


def test_login_saves_token(db, token_file, requests_mock, monkeypatch):
    monkeypatch.setenv("EPI_USERNAME", "mcp-user")
    monkeypatch.setenv("EPI_PASSWORD", "mcp-pass")
    requests_mock.post(
        f"{BASE}/api/login", json={"token": VALID_TOKEN, "refresh_token": "r1"}
    )
    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})

    out = parse(srv.episciences_login("mcp-user", "mcp-pass"))
    assert out["ok"] is True
    assert out["token_preview"].startswith(VALID_TOKEN[:8])
    assert VALID_TOKEN not in out.values()  # never leak the token
    assert json.loads(token_file.read_text())["episciences"]["access"] == VALID_TOKEN


def test_login_bad_credentials(db, token_file, requests_mock):
    requests_mock.post(
        f"{BASE}/api/login", status_code=401, json={"code": 401, "message": "Invalid credentials."}
    )
    out = parse(srv.episciences_login("u", "wrong"))
    assert out["ok"] is False
    assert "Invalid" in out["error"]


def test_save_token_validates_before_saving(db, token_file, requests_mock):
    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    out = parse(srv.episciences_save_token(VALID_TOKEN, "r1"))
    assert out["ok"] is True
    assert out["validated"] is True
    assert json.loads(token_file.read_text())["episciences"]["access"] == VALID_TOKEN


def test_save_token_rejects_invalid_token(db, token_file, requests_mock):
    requests_mock.get(f"{BASE}/api/me", status_code=401, json={"code": 401})
    out = parse(srv.episciences_save_token("bad-token"))
    assert out["ok"] is False
    assert "NOT saved" in out["error"]
    assert not token_file.exists()


def test_save_token_rejects_empty(db):
    out = parse(srv.episciences_save_token("   "))
    assert out["ok"] is False


def test_token_status_unstored(token_file):
    out = parse(srv.episciences_token_status())
    assert out["stored"] is False
    assert "hint" in out


def test_token_status_stored_and_working(db, token_file, requests_mock):
    from episciences.episciences_api import TokenStorage

    TokenStorage().save(VALID_TOKEN, "r1")
    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    out = parse(srv.episciences_token_status())
    assert out["stored"] is True
    assert out["works"] is True
    assert "token" not in out  # no secret leak


def test_logout(token_file):
    from episciences.episciences_api import TokenStorage

    storage = TokenStorage()
    storage.save(VALID_TOKEN, None)
    out = parse(srv.episciences_logout())
    assert out["removed"] is True
    assert storage.load() is None


def test_list_papers(db, stored_token, requests_mock):
    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    requests_mock.get(
        f"{BASE}/api/papers/",
        json={
            "hydra:member": [
                {"paperid": 1, "docid": 1, "doi": "d1", "status": 16, "title": "A"},
                {"paperid": 2, "docid": 2, "doi": "d2", "status": 19, "title": "B"},
            ]
        },
    )
    out = parse(srv.episciences_list_papers())
    assert out["count"] == 2
    assert out["papers"][1]["status_label"] == "Copy editing"

    out = parse(srv.episciences_list_papers(status=16))
    assert out["count"] == 1
    assert out["papers"][0]["paperid"] == 1


def test_get_paper(db, stored_token, requests_mock):
    from .test_paper import NESTED_PAPER

    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    requests_mock.get(
        f"{BASE}/api/papers/", json={"hydra:member": [{"paperid": 18597, "status": 16}]}
    )
    requests_mock.get(f"{BASE}/api/papers/18597", json=NESTED_PAPER)

    out = parse(srv.episciences_get_paper("18597"))
    assert out["title"] == "A new perspective in linear Cauchy Elasticity"
    assert out["status"] == 16  # from the listing fallback
    assert out["status_label"] == "Published"
    assert out["authors"][0]["surname"] == "Smith"


def test_get_paper_accepts_api_url(db, stored_token, requests_mock):
    from .test_paper import LEGACY_PAPER

    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    requests_mock.get(f"{BASE}/api/papers/", json={"hydra:member": []})
    requests_mock.get(f"{BASE}/api/papers/12489", json=LEGACY_PAPER)
    out = parse(srv.episciences_get_paper(f"{BASE}/api/papers/12489"))
    assert out["title"] == "Legacy paper title"


def test_get_paper_not_found(db, stored_token, requests_mock):
    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    requests_mock.get(f"{BASE}/api/papers/", json={"hydra:member": []})
    requests_mock.get(f"{BASE}/api/papers/1", status_code=404, json={"code": 404})
    out = parse(srv.episciences_get_paper("1"))
    assert out["ok"] is False


def test_list_users(db, stored_token, requests_mock):
    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    requests_mock.get(
        f"{BASE}/api/users",
        json={"hydra:member": [{"uid": 7, "screenName": "jdoe", "email": "j@x.org"}]},
    )
    out = parse(srv.episciences_list_users())
    assert out["count"] == 1
    assert out["users"][0]["screenName"] == "jdoe"


def test_mcp_server_lists_tools():
    import asyncio

    tools = asyncio.run(srv.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "episciences_login",
        "episciences_save_token",
        "episciences_token_status",
        "episciences_logout",
        "episciences_list_papers",
        "episciences_get_paper",
        "episciences_list_users",
    }
