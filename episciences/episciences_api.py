#!/usr/bin/env python
"""Client library for the Episciences API (https://api.episciences.org).

Features
--------
- Robust HTTP layer: retries with exponential backoff on transient failures
  (429/5xx), honoring ``Retry-After``, sane timeouts and typed exceptions.
- Automatic token lifecycle: token loaded from OpenCode's ``auth.json``,
  transparent refresh when the 1h access token expires, credential based
  login (explicit, env vars ``EPI_USERNAME``/``EPI_PASSWORD`` for CI, or
  interactive prompt when allowed).
"""
from __future__ import annotations

import base64
import getpass
import json
import logging
import os
import tempfile
import time
from pathlib import Path

import requests
from jsonpath_ng.ext import parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.episciences.org"

# Endpoints that must keep a trailing slash (the API 301-redirects the bare
# form, which would downgrade a POST into a GET).
TRAILING_SLASH_PATHS = frozenset(
    ["/api/papers", "/api/volumes", "/api/sections", "/api/news", "/api/feed"]
)


################################################################
# Exceptions
################################################################


class EpisciencesError(Exception):
    """Base class for all errors raised by this module."""


class HttpErrorCode(EpisciencesError):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg
        super().__init__(code, msg)

    def __str__(self):
        return f"HTTP {self.code}: {self.msg}"


class AuthenticationError(HttpErrorCode):
    """HTTP 401: missing, invalid or expired credentials."""


class AuthorizationError(HttpErrorCode):
    """HTTP 403: authenticated but not allowed."""


class NotFoundError(HttpErrorCode):
    """HTTP 404."""


class RateLimitError(HttpErrorCode):
    """HTTP 429: too many requests (should be rare thanks to retries)."""


class ServerError(HttpErrorCode):
    """HTTP 5xx after exhausting the retries."""


class ProtocolError(EpisciencesError):
    """The server answered something we cannot parse."""


class NetworkError(EpisciencesError):
    """Connection-level failure (DNS, timeout, reset, ...)."""


################################################################
# Helpers
################################################################


def to_json(data):
    if isinstance(data, QueryAbleObject):
        data = data.json

    # If it is a dictionary, scan all keys and values
    if isinstance(data, dict):
        keys = data.keys()
        for key in keys:
            data[key] = to_json(data[key])

    # If it is a list, scan all items
    elif isinstance(data, list):
        data = [to_json(e) for e in data]

    return data


def jwt_expiry(token):
    """Return the expiry timestamp (epoch seconds) of a JWT, or None."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        exp = data.get("exp")
        return int(exp) if exp else None
    except Exception:  # not a JWT, malformed, ...
        return None


################################################################
# QueryAbleObject
################################################################


class QueryAbleObject:
    def __init__(self, _json):
        self.json = _json

    def extract_values(self, expr):
        return [m.value for m in parse(expr).find(self.json)]

    def is_leaf(self, m):
        if isinstance(m, list) and len(m) == 1:
            if not isinstance(m[0], list) and not isinstance(m[0], dict):
                return True

    def get(self, key, default=None):
        m = self.extract_values(f"$..{key}")
        if m:
            if self.is_leaf(m):
                return m[0]
            elif isinstance(m, str):
                return m
            return QueryAbleObject(m)
        elif default is not None:
            return default

        raise AttributeError(key)

    def get_or_none(self, key, default=None):
        try:
            return self.get(key)
        except AttributeError:
            return default

    def __getattr__(self, key):
        try:
            return self.get(key)
        except AttributeError:
            raise AttributeError(key)

    def __iter__(self):
        if isinstance(self.json, list):

            def get_leaf(e):
                if self.is_leaf(e):
                    return e[0]
                elif isinstance(e, str):
                    return e
                return QueryAbleObject(e)

            t = [get_leaf(e) for e in self.json]
            return t.__iter__()
        return self.json.__iter__()

    def __repr__(self):
        if self.is_leaf(self.json):
            return self.json[0].__repr__()
        return self.json.__repr__()

    def __getitem__(self, idx):
        return QueryAbleObject(self.json[idx])

    def join(self, sep):
        return sep.join(self.json)

    def items(self):
        return self.json.items()

    def to_json(self):
        return to_json(self)


################################################################
# Paper
################################################################


class EpiSciencesPaper(QueryAbleObject):
    """A paper returned by ``/api/papers/{docid}``.

    The API moved to a nested ``document`` (JATS-like) representation; these
    properties work with both the legacy flat shape and the nested one.
    """

    def __init__(self, _json, list_data=None):
        super().__init__(_json)
        # Optional data from the /api/papers listing (contains e.g. status)
        self.list_data = list_data or {}

    @staticmethod
    def _unwrap(value):
        while isinstance(value, QueryAbleObject):
            value = value.json
        return value

    def _match(self, key):
        """Return the raw value of ``key`` searched recursively: the match
        value itself when unique (not wrapped in an extra list), otherwise
        the list of matches; ``None`` when absent."""
        matches = self.extract_values(f"$..{key}")
        if not matches:
            return None
        if len(matches) == 1:
            return self._unwrap(matches[0])
        return [self._unwrap(m) for m in matches]

    def _first(self, value):
        while isinstance(value, QueryAbleObject):
            value = value.json
        while isinstance(value, list):
            if not value:
                return None
            value = value[0]
            while isinstance(value, QueryAbleObject):
                value = value.json
        if isinstance(value, str):
            return value.strip()
        return value

    @property
    def paperid(self):
        return self.get_or_none("paperid")

    @property
    def docid(self):
        return self.get_or_none("docid") or self.get_or_none("paperid")

    @property
    def doi(self):
        """The paper's own DOI (the detail document also contains the DOIs
        of its bibliography, so only the top level/listing is trusted)."""
        if isinstance(self.json, dict) and "doi" in self.json:
            return self.json["doi"]
        if self.list_data and "doi" in self.list_data:
            return self.list_data["doi"]
        return None

    @property
    def title(self):
        title = self.get_or_none("title")
        if title is None:
            raise AttributeError("title")
        return self._first(title)

    @property
    def abstract(self):
        abstract = self.get_or_none("abstract")
        if abstract is not None and hasattr(abstract, "value"):
            abstract = abstract.value
        return self._first(abstract)

    @property
    def status(self):
        """Status code. The detail response embeds several ``status``
        entries (version history) and may not carry the current one at the
        top level, so we look at the raw top level first, then the listing
        data, then the history entries."""
        if isinstance(self.json, dict) and "status" in self.json:
            return self.json["status"]
        if self.list_data and "status" in self.list_data:
            return self.list_data["status"]
        m = self._match("status")
        if isinstance(m, list):
            for v in m:
                if isinstance(v, int):
                    return v
                if isinstance(v, dict) and "id" in v:
                    return v["id"]
            return None
        return m

    @property
    def status_label(self):
        code = self.status
        return EpisciencesDB.getStatusFromCode(code) if code is not None else None

    @property
    def dates(self):
        return self.get_or_none("dates")

    @property
    def first_submission_date(self):
        dates = self.dates
        if dates is None:
            return None
        return dates.get_or_none("first_submission_date")

    @property
    def contributors(self):
        return self.get_or_none("contributors")

    @property
    def authors(self):
        """Normalized list of ``{given_name, surname, orcid, affiliations}``."""
        persons = self._match("person_name")
        if persons is None:
            return []
        if isinstance(persons, dict):
            persons = [persons]
        if not isinstance(persons, list):
            return []

        authors = []
        for person in persons:
            person = self._unwrap(person)
            if not isinstance(person, dict):
                continue
            affiliations = []
            affs = self._unwrap(person.get("affiliations"))
            if isinstance(affs, dict):
                affs = [affs]
            for aff in affs if isinstance(affs, list) else []:
                aff = self._unwrap(aff)
                if isinstance(aff, dict):
                    institutions = self._unwrap(aff.get("institution"))
                    if institutions is None:
                        institutions = aff.get("institution_name")
                    if isinstance(institutions, dict):
                        institutions = [institutions]
                    for inst in institutions if isinstance(institutions, list) else []:
                        inst = self._unwrap(inst)
                        if isinstance(inst, dict):
                            name = self._first(inst.get("institution_name"))
                            if name:
                                affiliations.append(name)
                        elif inst:
                            affiliations.append(str(inst))
                elif aff:
                    affiliations.append(str(aff))
            authors.append(
                {
                    "given_name": self._first(person.get("given_name")),
                    "surname": self._first(person.get("surname")),
                    "orcid": self._first(person.get("ORCID")),
                    "affiliations": affiliations,
                }
            )
        return authors

    @property
    def keywords(self):
        keywords = self._match("keywords")
        if keywords is None:
            keywords = self._match("keyword")
        if keywords is None:
            return []
        if isinstance(keywords, dict):
            keywords = [keywords]
        out = []
        for kw in keywords:
            kw = self._unwrap(kw)
            if isinstance(kw, dict):
                value = kw.get("value", kw)
            else:
                value = kw
            if isinstance(value, list):
                value = [self._first(v) for v in value]
            out.append(value)
        return out

    @property
    def files(self):
        files = self._match("files")
        if files is None:
            return []
        if not isinstance(files, list):
            files = [files]
        links = []
        for f in files:
            f = self._unwrap(f)
            while isinstance(f, list):
                f = self._unwrap(f[0]) if f else None
            if isinstance(f, dict) and "link" in f:
                links.append(self._first(f["link"]))
            elif isinstance(f, str):
                links.append(f)
        return links


################################################################
# Token storage
################################################################


class TokenStorage:
    """Stores the Episciences credentials inside OpenCode's ``auth.json``.

    The file (``~/.local/share/opencode/auth.json`` by default, honoring
    ``XDG_DATA_HOME``) holds one entry per provider/MCP server. We follow the
    same shape as OpenCode's OAuth entries::

        {"episciences": {"type": "oauth", "access": ..., "refresh": ...,
                          "expires": <epoch ms>, "journal": "jtcam"}}

    Other entries present in the file are preserved. ``EPI_TOKEN_FILE`` can
    point to an alternative file. As a read-only fallback, a legacy
    ``token.json`` (``{"token": ..., "refresh_token": ...}``) in the current
    directory is honored when the main storage has no entry.
    """

    KEY = "episciences"
    LEGACY_FILE = "token.json"

    def __init__(self, path=None):
        self.path = Path(path) if path else self.default_path()

    @staticmethod
    def default_path():
        env = os.environ.get("EPI_TOKEN_FILE")
        if env:
            return Path(env)
        data_home = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )
        return Path(data_home) / "opencode" / "auth.json"

    # -- serialization -------------------------------------------------

    @staticmethod
    def _entry_from_token(token, refresh_token=None, journal=None, expires=None):
        if expires is None:
            expires = jwt_expiry(token or "")
        entry = {"type": "oauth", "access": token, "refresh": refresh_token}
        if expires:
            entry["expires"] = int(expires * 1000)  # OpenCode stores epoch ms
        if journal:
            entry["journal"] = journal
        return entry

    @staticmethod
    def _token_from_entry(entry):
        if not isinstance(entry, dict):
            return None
        token = entry.get("access") or entry.get("token")
        if not token:
            return None
        stored = {"token": token, "refresh_token": entry.get("refresh")}
        return stored

    # -- I/O ------------------------------------------------------------

    def _read_file(self):
        try:
            with open(self.path) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("cannot read token file %s: %s", self.path, e)
            return {}

    def _write_file(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".auth", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def load(self):
        """Return the stored token as ``{"token": ..., "refresh_token": ...}``
        or ``None`` when absent."""
        data = self._read_file()
        stored = self._token_from_entry(data.get(self.KEY))
        if stored:
            return stored
        # legacy fallback (read-only migration path)
        try:
            with open(self.LEGACY_FILE) as f:
                legacy = json.load(f)
            if isinstance(legacy, dict) and "token" in legacy:
                return {"token": legacy["token"], "refresh_token": legacy.get("refresh_token")}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return None

    def save(self, token, refresh_token=None, journal=None):
        if not token:
            raise ValueError("refusing to save an empty token")
        data = self._read_file()
        data[self.KEY] = self._entry_from_token(token, refresh_token, journal)
        self._write_file(data)

    def clear(self):
        data = self._read_file()
        if self.KEY in data:
            del data[self.KEY]
            self._write_file(data)

    def status(self):
        """Return a dict describing the stored token (no network call)."""
        stored = self.load()
        if not stored:
            return {"stored": False}
        exp = jwt_expiry(stored["token"])
        now = time.time()
        return {
            "stored": True,
            "file": str(self.path),
            "has_refresh_token": bool(stored.get("refresh_token")),
            "expires_at": exp,
            "expired": exp is not None and exp <= now,
            "expires_in_seconds": (exp - now) if exp is not None else None,
        }


################################################################
# Database connection
################################################################


class EpisciencesDB:
    status_codes = {
        -1: "Unknown",
        19: "Copy editing",
        16: "Published",
        6: "Obsolete",
        4: "Accepted",
        5: "Refused",
        0: "submitted",
        2: "In review",
        7: "Pending minor revision",
        15: "Pending major revision",
        12: "Reviewed",
        17: "Abandoned",
    }

    @staticmethod
    def getStatusFromCode(code):
        if code in EpisciencesDB.status_codes:
            status = EpisciencesDB.status_codes[code]
        else:
            status = "Unknown"
        return status

    # rvid = 23 => JTCAM
    def __init__(
        self,
        rvid=23,
        token=None,
        *,
        username=None,
        password=None,
        journal_code=None,
        interactive=False,
        timeout=None,
        base_url=None,
        token_file=None,
        max_retries=5,
        retry_backoff=1.0,
        auto_authenticate=True,
    ):
        self.base_url = (base_url or os.environ.get("EPI_API_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else float(os.environ.get("EPI_TIMEOUT", 30))
        self.token = {"token": token} if token else None
        self.provided_token = token
        self.credentials = (username, password) if username or password else (None, None)
        self.journal_code = journal_code or os.environ.get("EPI_JOURNAL") or "jtcam"
        self.interactive = interactive
        self.rvid = rvid
        self.storage = TokenStorage(token_file)
        self.session = self._make_session(max_retries, retry_backoff)
        if auto_authenticate:
            self.authenticate()

    # -- HTTP plumbing ---------------------------------------------------

    @staticmethod
    def _make_session(max_retries, retry_backoff):
        retry = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            backoff_factor=retry_backoff,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    @staticmethod
    def _normalize_path(path):
        if not path.startswith("/"):
            path = "/" + path
        base = path.split("?")[0].rstrip("/")
        if base in TRAILING_SLASH_PATHS and not path.endswith("/"):
            path += "/"
        return path

    @staticmethod
    def _error_from_response(resp, req):
        msg = None
        try:
            body = resp.json()
            msg = body.get("message") or body.get("hydra:description")
        except ValueError:
            text = (resp.text or "").strip()
            msg = text[:200] if text else None
        classes = {
            401: AuthenticationError,
            403: AuthorizationError,
            404: NotFoundError,
            429: RateLimitError,
        }
        cls = classes.get(resp.status_code)
        if resp.status_code >= 500:
            cls = ServerError
        if cls is None:
            cls = HttpErrorCode
        return cls(resp.status_code, f"Failed to perform request: {req}" + (f" ({msg})" if msg else ""))

    def _request(self, method, path, params=None, json_body=None, auth=True):
        url = self.base_url + self._normalize_path(path)
        headers = {"accept": "application/json"}
        if auth and self.token and "token" in self.token:
            headers["Authorization"] = f"Bearer {self.token['token']}"
        try:
            resp = self.session.request(
                method, url, params=params, json=json_body, headers=headers, timeout=self.timeout
            )
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Cannot reach {url}: {e}") from e

        if resp.status_code >= 400:
            raise self._error_from_response(resp, path)
        try:
            return resp.json()
        except ValueError as e:
            raise ProtocolError(f"Non-JSON response for {path}: {resp.text[:200]!r}") from e

    def _authenticated_get(self, path, params=None):
        """GET with a single transparent refresh+retry on token expiry."""
        try:
            return self._request("GET", path, params=params)
        except AuthenticationError:
            if self.refresh_token():
                return self._request("GET", path, params=params)
            raise

    # -- public request API (backward compatible) -------------------------

    def epi_get(self, req, **kwargs):
        data = self._authenticated_get(req, params=kwargs or None)
        if isinstance(data, dict) and "hydra:member" in data:
            return data["hydra:member"]
        return data

    # -- authentication ----------------------------------------------------

    def _resolve_credentials(self):
        username, password = self.credentials
        if username is None and os.environ.get("EPI_USERNAME"):
            username = os.environ["EPI_USERNAME"]
        if password is None and os.environ.get("EPI_PASSWORD"):
            password = os.environ["EPI_PASSWORD"]
        return username, password

    def fetch_token(self, username=None, password=None):
        """Login and store the new token (persisted to the token storage)."""
        if username is None or password is None:
            env_user, env_pass = self._resolve_credentials()
            username = username if username is not None else env_user
            password = password if password is not None else env_pass
        if username is None and self.interactive:
            username = input("login:")
        if password is None and self.interactive:
            password = getpass.getpass("password: ")
        if not username or not password:
            raise AuthenticationError(
                401,
                "Missing credentials: provide username/password, set "
                "EPI_USERNAME/EPI_PASSWORD, or allow interactive login",
            )

        payload = {"username": username, "password": password}
        if self.journal_code:
            payload["code"] = self.journal_code
        data = self._request("POST", "/api/login", json_body=payload, auth=False)

        if not isinstance(data, dict) or "token" not in data:
            raise AuthenticationError(401, f"Unexpected login response: {str(data)[:200]}")
        self.token = {"token": data["token"], "refresh_token": data.get("refresh_token")}
        self.write_token_to_file()
        return self.token

    def refresh_token(self):
        """Refresh the access token. Returns True on success; never clobbers
        a stored token with an error payload."""
        refresh = (self.token or {}).get("refresh_token")
        if not refresh:
            return False
        try:
            data = self._request(
                "POST", "/api/token/refresh", json_body={"refresh_token": refresh}, auth=False
            )
        except HttpErrorCode as e:
            logger.info("token refresh failed: %s", e)
            return False
        if not isinstance(data, dict) or "token" not in data:
            logger.info("token refresh returned an unexpected payload")
            return False
        self.token = {"token": data["token"], "refresh_token": data.get("refresh_token", refresh)}
        self.write_token_to_file()
        return True

    def read_token_from_file(self):
        stored = self.storage.load()
        if stored:
            self.token = stored
        return self.token

    def write_token_to_file(self):
        if self.token and "token" in self.token:
            self.storage.save(
                self.token["token"],
                self.token.get("refresh_token"),
                journal=self.journal_code,
            )

    def forget_token(self):
        self.storage.clear()
        self.token = None

    def authenticate(self):
        """Ensure ``self.token`` holds a working access token.

        Order: explicitly provided token > explicit credentials > stored
        token (with refresh) > credentials from the environment >
        interactive prompt (only when ``interactive=True``).
        """
        # 1. explicitly provided token
        if self.provided_token is not None:
            self.token = {"token": self.provided_token}
            if self.check_authentication():
                return
            self.token = None

        # 2. explicit credentials: login right away
        username, password = self.credentials
        if username and password:
            self.fetch_token(username, password)
            if self.check_authentication():
                return
            raise AuthenticationError(401, "Login did not produce a working token")

        # 3. stored token
        self.read_token_from_file()
        if self.token and self.check_authentication():
            return

        # 4. refresh the stored token
        if self.token and self.refresh_token() and self.check_authentication():
            return

        # 5. credentials from the environment (e.g. GitLab CI variables)
        env_user, env_pass = self._resolve_credentials()
        if env_user and env_pass:
            self.fetch_token(env_user, env_pass)
            if self.check_authentication():
                return

        # 6. interactive prompt, when allowed
        if self.interactive:
            self.fetch_token()
            if self.check_authentication():
                return

        if self.token is None:
            raise AuthenticationError(
                401,
                "No valid Episciences credentials: login failed or no "
                "credentials available (set EPI_USERNAME/EPI_PASSWORD or "
                "login through the MCP server)",
            )
        raise AuthenticationError(401, "Stored Episciences token is not valid")

    def check_authentication(self):
        if not self.token or "token" not in self.token:
            return False
        try:
            self._request("GET", "/api/me")
        except AuthenticationError:
            logger.info("Expired token")
            return False
        return True

    # -- data access -------------------------------------------------------

    def list_papers(self):
        params = {"pagination": "false"}
        if self.journal_code:
            params["rvcode"] = self.journal_code
        else:
            params["rvid"] = self.rvid
        return self.epi_get("/api/papers/", **params)

    def list_users(self):
        return self.epi_get("/api/users", pagination="false")

    def get_user(self, uid):
        return self.epi_get(f"/api/users/{uid}")

    def get_paper(self, uid, list_data=None):
        r = self._authenticated_get(f"/api/papers/{uid}")
        return EpiSciencesPaper(r, list_data=list_data)


################################################################
