"""Tests for the HTTP layer of EpisciencesDB: URL building, params,
error mapping, hydra parsing."""

import pytest
from episciences.episciences_api import (
    AuthenticationError,
    EpisciencesDB,
    HttpErrorCode,
    NetworkError,
    NotFoundError,
    ProtocolError,
    ServerError,
)

from .conftest import BASE


def test_session_has_retry_policy(db):
    retry = db.session.get_adapter(f"{BASE}/api/papers/").max_retries
    assert retry.status_forcelist == (429, 500, 502, 503, 504)
    assert retry.total == 5
    assert retry.raise_on_status is False
    assert retry.respect_retry_after_header is True


def test_default_timeout(db):
    assert db.timeout == 30.0


def test_timeout_env_override(token_file, monkeypatch):
    monkeypatch.setenv("EPI_TIMEOUT", "7")
    assert EpisciencesDB(auto_authenticate=False).timeout == 7.0


def test_normalize_path():
    assert EpisciencesDB._normalize_path("/api/papers") == "/api/papers/"
    assert EpisciencesDB._normalize_path("/api/papers/") == "/api/papers/"
    assert EpisciencesDB._normalize_path("api/me") == "/api/me"
    assert EpisciencesDB._normalize_path("/api/papers/12489") == "/api/papers/12489"


def test_epi_get_hydra_member(authed_db, requests_mock):
    requests_mock.get(
        f"{BASE}/api/papers/",
        json={"hydra:member": [{"paperid": 1}], "hydra:totalItems": 1},
    )
    assert authed_db.epi_get("/api/papers/") == [{"paperid": 1}]


def test_epi_get_plain_object(authed_db, requests_mock):
    requests_mock.get(f"{BASE}/api/me", json={"email": "u@example.org"})
    assert authed_db.epi_get("/api/me")["email"] == "u@example.org"


def test_query_params_are_properly_encoded(authed_db, requests_mock):
    from urllib.parse import parse_qs

    m = requests_mock.get(f"{BASE}/api/papers/", json={"hydra:member": []})
    authed_db.epi_get("/api/papers/", rvcode="jtcam", search="elastic wave")
    query = parse_qs(m.last_request.query)
    assert query["rvcode"] == ["jtcam"]
    assert query["search"] == ["elastic wave"]


def test_list_value_params_are_repeated(authed_db, requests_mock):
    m = requests_mock.get(f"{BASE}/api/papers/", json={"hydra:member": []})
    authed_db.epi_get("/api/papers/", year=[2023, 2024])
    assert "year=2023" in m.last_request.query
    assert "year=2024" in m.last_request.query


def test_list_papers_uses_rvcode(authed_db, requests_mock):
    m = requests_mock.get(f"{BASE}/api/papers/", json={"hydra:member": []})
    authed_db.list_papers()
    assert "rvcode=jtcam" in m.last_request.query
    assert "pagination=false" in m.last_request.query


def test_trailing_slash_is_enforced(authed_db, requests_mock):
    m = requests_mock.get(f"{BASE}/api/papers/", json={"hydra:member": []})
    authed_db.epi_get("/api/papers", pagination="false")
    assert m.called


def test_404_maps_to_not_found(authed_db, requests_mock):
    requests_mock.get(
        f"{BASE}/api/papers/999999",
        status_code=404,
        json={"hydra:title": "An error occurred", "hydra:description": "Not Found"},
    )
    with pytest.raises(NotFoundError) as exc:
        authed_db.get_paper(999999)
    assert exc.value.code == 404


def test_401_maps_to_authentication_error(authed_db, requests_mock):
    requests_mock.get(f"{BASE}/api/me", status_code=401, json={"code": 401})
    requests_mock.post(
        f"{BASE}/api/token/refresh",
        status_code=401,
        json={"code": 401, "message": "Invalid JWT Refresh Token"},
    )
    with pytest.raises(AuthenticationError):
        authed_db.epi_get("/api/me")


def test_500_maps_to_server_error(authed_db, requests_mock):
    requests_mock.get(f"{BASE}/api/papers/", status_code=500, text="boom")
    with pytest.raises(ServerError):
        authed_db.epi_get("/api/papers/")


def test_error_message_is_extracted_from_body(authed_db, requests_mock):
    requests_mock.get(
        f"{BASE}/api/papers/1",
        status_code=404,
        json={"hydra:description": "Not Found"},
    )
    with pytest.raises(NotFoundError, match="Not Found"):
        authed_db.get_paper(1)


def test_non_json_response_maps_to_protocol_error(authed_db, requests_mock):
    requests_mock.get(f"{BASE}/api/papers/", status_code=200, text="<html>oops</html>")
    with pytest.raises(ProtocolError):
        authed_db.epi_get("/api/papers/")


def test_connection_error_maps_to_network_error(authed_db, monkeypatch):
    import requests

    def raise_connection_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(authed_db.session, "request", raise_connection_error)
    with pytest.raises(NetworkError):
        authed_db.epi_get("/api/papers/")


def test_all_errors_are_http_error_code_subclasses(authed_db, requests_mock):
    """Backward compatibility: legacy code catching HttpErrorCode keeps working."""
    requests_mock.get(f"{BASE}/api/papers/", status_code=502, text="bad gateway")
    with pytest.raises(HttpErrorCode):
        authed_db.epi_get("/api/papers/")


def test_get_paper_returns_paper_object(authed_db, requests_mock):
    requests_mock.get(f"{BASE}/api/papers/12489", json={"paperid": 12489, "title": "T"})
    p = authed_db.get_paper(12489)
    assert p.paperid == 12489


def test_get_user(authed_db, requests_mock):
    requests_mock.get(f"{BASE}/api/users/42", json={"uid": 42})
    assert authed_db.get_user(42)["uid"] == 42


def test_list_users(authed_db, requests_mock):
    m = requests_mock.get(
        f"{BASE}/api/users", json={"hydra:member": [{"uid": 1}]}
    )
    assert authed_db.list_users() == [{"uid": 1}]
    assert "pagination=false" in m.last_request.query
