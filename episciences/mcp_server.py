#!/usr/bin/env python
"""MCP server exposing the Episciences API.

Tools
-----
- ``episciences_login``: obtain and persist a token from username/password.
- ``episciences_save_token``: validate and persist an existing token.
- ``episciences_token_status``: report on the stored token (no secrets).
- ``episciences_logout``: remove the stored token.
- ``episciences_list_papers``: list papers of the journal, optionally
  filtered by status.
- ``episciences_get_paper``: full record of one paper.
- ``episciences_list_users``: list journal users.

Run with ``episciences-mcp`` (stdio transport) and register it in your MCP
client, e.g. for OpenCode::

    opencode mcp add episciences --global -- episciences-mcp
"""
from __future__ import annotations

import json
import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from .episciences_api import (
    EpisciencesDB,
    EpisciencesError,
    HttpErrorCode,
    TokenStorage,
    jwt_expiry,
)

logger = logging.getLogger("episciences.mcp")

mcp = FastMCP(
    "episciences",
    instructions=(
        "Access to the Episciences API (https://api.episciences.org): manage "
        "the API token and query papers and users of an Episciences journal "
        "(JTCAM by default)."
    ),
)


################################################################
# helpers
################################################################


def _default_journal():
    return os.environ.get("EPI_JOURNAL") or "jtcam"


def _masked(token):
    if not token:
        return None
    return f"{token[:8]}...({len(token)} chars)"


def _dump(data):
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _db(token=None, journal=None, **kwargs):
    """Build a connection without triggering the authentication chain."""
    return EpisciencesDB(
        token=token,
        journal_code=journal or _default_journal(),
        interactive=False,
        auto_authenticate=False,
        **kwargs,
    )


################################################################
# token management tools
################################################################


@mcp.tool()
def episciences_login(username: str, password: str, journal: str = "") -> str:
    """Log in to the Episciences API with your username and API password,
    then store the token (with its refresh token) in OpenCode's auth.json.
    The token is valid for 1 hour and is renewed automatically afterwards.
    """
    try:
        conn = _db(username=username, password=password, journal=journal or None)
        conn.authenticate()
        token = conn.token or {}
        status = conn.storage.status()
        return _dump(
            {
                "ok": True,
                "journal": conn.journal_code,
                "token_preview": _masked(token.get("token")),
                "has_refresh_token": bool(token.get("refresh_token")),
                "stored_at": status.get("file"),
                "expires_at": status.get("expires_at"),
            }
        )
    except EpisciencesError as e:
        return _dump({"ok": False, "error": str(e)})


@mcp.tool()
def episciences_save_token(token: str, refresh_token: str = "") -> str:
    """Save an existing Episciences API token (and optionally its refresh
    token) after validating it against the API. Use this when you obtained
    a token by other means, e.g. from a CI job or a colleague.
    """
    if not token or not token.strip():
        return _dump({"ok": False, "error": "empty token"})
    token = token.strip()
    rt: str | None = (refresh_token or "").strip() or None

    conn = _db(token=token)
    valid = conn.check_authentication()
    if not valid:
        return _dump(
            {
                "ok": False,
                "error": "token was rejected by the API (invalid or expired); "
                "it was NOT saved",
                "token_preview": _masked(token),
            }
        )
    storage = TokenStorage()
    storage.save(token, rt, journal=_default_journal())
    return _dump(
        {
            "ok": True,
            "validated": True,
            "token_preview": _masked(token),
            "stored_at": str(storage.path),
            "expires_at": jwt_expiry(token),
        }
    )


@mcp.tool()
def episciences_token_status() -> str:
    """Report the state of the stored Episciences token: presence, expiry,
    and whether it currently works against the API. Never reveals the token.
    """
    storage = TokenStorage()
    status = storage.status()
    if not status.get("stored"):
        return _dump(
            {
                "stored": False,
                "hint": "run episciences_login or episciences_save_token first",
            }
        )
    conn = _db()
    conn.token = conn.storage.load()
    status["works"] = conn.check_authentication()
    return _dump(status)


@mcp.tool()
def episciences_logout() -> str:
    """Remove the stored Episciences token from the token storage."""
    storage = TokenStorage()
    had = storage.load() is not None
    storage.clear()
    return _dump({"ok": True, "removed": had, "file": str(storage.path)})


################################################################
# query tools
################################################################


def _paper_summary(p):
    """Summary of a paper entry from the listing (plain dict) or an
    EpiSciencesPaper."""

    def field(name):
        if isinstance(p, dict):
            return p.get(name)
        return p.get_or_none(name)

    status = field("status")
    return {
        "paperid": field("paperid"),
        "docid": field("docid"),
        "doi": field("doi"),
        "status": status,
        "status_label": EpisciencesDB.getStatusFromCode(status),
        "title": field("title"),
    }


@mcp.tool()
def episciences_list_papers(status: int = -999) -> str:
    """List the papers of the journal (JTCAM by default). Optionally filter
    by numeric status, e.g. 16=published, 19=copy editing, 2=in review,
    4=accepted, 5=refused, 0=submitted, 15=pending major revision,
    7=pending minor revision. Returns paperid, docid, doi, title and status.
    """
    try:
        conn = _db()
        conn.authenticate()
        papers = conn.list_papers()
        out = []
        for p in papers:
            if not isinstance(p, dict):
                continue
            if status != -999 and p.get("status") != status:
                continue
            q = _paper_summary(p)
            q["title"] = q["title"] or p.get("document", {}).get("title")
            out.append(q)
        return _dump({"count": len(out), "papers": out})
    except EpisciencesError as e:
        return _dump({"ok": False, "error": str(e)})


@mcp.tool()
def episciences_get_paper(paper_id: str) -> str:
    """Fetch the full record of one paper, identified by its docid,
    paperid, DOI or the URL of its API endpoint."""
    paper_id = str(paper_id).strip()
    if "/api/papers/" in paper_id:
        paper_id = paper_id.split("/api/papers/")[1].rstrip("/")
    try:
        conn = _db()
        conn.authenticate()
        listing = {str(p.get("paperid")): p for p in conn.list_papers() if isinstance(p, dict)}
        list_data = listing.get(paper_id) or {}
        p = conn.get_paper(paper_id, list_data=list_data)
        data = {
            "paperid": p.paperid,
            "docid": p.docid,
            "doi": p.doi,
            "title": p.title,
            "status": p.status,
            "status_label": p.status_label,
            "abstract": p.abstract,
            "authors": p.authors,
            "keywords": p.keywords,
            "files": p.files,
            "first_submission_date": p.first_submission_date,
            "raw": p.json,
        }
        return _dump(data)
    except EpisciencesError as e:
        return _dump({"ok": False, "error": str(e)})


@mcp.tool()
def episciences_list_users() -> str:
    """List the users (editorial board, authors, reviewers...) of the
    journal with their uid, name and email. Requires a valid token."""
    try:
        conn = _db()
        conn.authenticate()
        users = conn.list_users()
        out = []
        for u in users:
            if not isinstance(u, dict):
                continue
            out.append(
                {
                    "uid": u.get("uid"),
                    "@id": u.get("@id"),
                    "screenName": u.get("screenName"),
                    "fullname": u.get("fullname"),
                    "email": u.get("email"),
                }
            )
        return _dump({"count": len(out), "users": out})
    except EpisciencesError as e:
        return _dump({"ok": False, "error": str(e)})


################################################################
# entry point
################################################################


def main():
    logging.basicConfig(
        level=os.environ.get("EPI_MCP_LOGLEVEL", "WARNING"),
        stream=sys.stderr,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
