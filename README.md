# episciences-api

Python client for the [Episciences API](https://api.episciences.org)
([OpenAPI docs](https://api.episciences.org/api/docs)) — query papers and
users of an Episciences journal (JTCAM by default), from Python, the command
line, a browser app or an MCP client.

## Installation

```sh
pip install git+https://github.com/JTCAM/episciences-api.git
# or, for the Streamlit explorator:
pip install "episciences-api[streamlit] @ git+https://github.com/JTCAM/episciences-api.git"
```

With poetry:

```sh
poetry install                      # library + CLI + MCP server
poetry install --extras streamlit   # + the browser app
poetry install --with dev           # + test dependencies
```

## Authentication

The API uses short-lived JWT tokens: the access token lives **1 hour**, the
refresh token about **1 month**. The client handles the full lifecycle
automatically — storage, refresh, and re-login — in this order:

1. an explicitly provided `token=`;
2. explicit `username=`/`password=`;
3. the stored token (renewed by refresh when expired);
4. the environment variables `EPI_USERNAME` / `EPI_PASSWORD`
   (the GitLab CI path);
5. an interactive prompt — only when `interactive=True` (CLI, Streamlit).

```python
import episciences as epi

# with credentials (e.g. in CI with EPI_USERNAME/EPI_PASSWORD set)
conn = epi.EpisciencesDB()          # journal 'jtcam' by default

papers = conn.list_papers()         # status, paperid, doi of every paper
paper = conn.get_paper(20086)       # full record (accepts docid or paperid)
print(paper.title, paper.status_label)
```

### Token storage

Tokens are stored in OpenCode's credential file
`~/.local/share/opencode/auth.json`, under an `"episciences"` key, alongside
the credentials of the other MCP servers. The file is written atomically with
`0600` permissions; unrelated entries are preserved. Overrides:

- `EPI_TOKEN_FILE` — use another file;
- `EPI_API_URL` — another API instance;
- `EPI_JOURNAL` — another journal code (default `jtcam`);
- `EPI_TIMEOUT` — request timeout in seconds (default `30`).

> A legacy `token.json` in the working directory (`{"token": ...,
> "refresh_token": ...}`) is still read, but new tokens are always written to
> `auth.json`.

Transient failures (HTTP 429/500/502/503/504) are retried automatically with
exponential backoff, and an expired access token is refreshed transparently
in the middle of a session.

## Command line

```
epi                     # list papers with their status
epi --paper 12489       # details of one paper
epi --json              # dump every paper to papers.json
epi --cmd /api/volumes  # run any GET request against the API
```

## Using the MCP server

The package ships an MCP (Model Context Protocol) server so that AI agents
(Claude, OpenCode, ...) can manage the token and query the journal.

### 1. Register the server

With OpenCode (recommended):

```sh
opencode mcp add episciences --global -- episciences-mcp
opencode mcp list          # should list the server as connected
```

Or manually in `~/.config/opencode/opencode.json`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "episciences": {
      "type": "local",
      "command": ["episciences-mcp"],
      "enabled": true
    }
  }
}
```

For Claude Desktop, add the equivalent block to
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "episciences": {
      "command": "episciences-mcp"
    }
  }
}
```

(Other stdio-capable MCP clients work the same way: run the command
`episciences-mcp` and talk to it over stdio.)

### 2. Authenticate once

Ask your agent to log in — it stores the token in `auth.json`:

> "Log in to Episciences with username `xxx` and password `yyy`"

This calls the `episciences_login` tool. Alternatively, to store a token
obtained elsewhere, use `episciences_save_token` (it is validated against the
API before being saved). Tokens are renewed automatically afterwards.

### 3. Tools

| Tool | Description |
| --- | --- |
| `episciences_login(username, password, journal?)` | Log in and store the token |
| `episciences_save_token(token, refresh_token?)` | Validate and store an existing token |
| `episciences_token_status()` | Presence, expiry and validity of the stored token (no secrets) |
| `episciences_logout()` | Remove the stored token |
| `episciences_list_papers(status?)` | List papers, optionally filtered by numeric status (16=published, 19=copy editing, 2=in review, ...) |
| `episciences_get_paper(paper_id)` | Full record of one paper (docid, paperid, DOI or API URL) |
| `episciences_list_users()` | List the journal users |

Example prompts once the server is connected:

- "List the JTCAM papers currently in copy editing"
- "Give me the abstract, authors and files of paper 20086"
- "Is my Episciences token still valid?"

## GitLab CI

`.gitlab-ci.yml` contains two jobs:

- `tests` — fully mocked, needs no credentials;
- `fetch-papers` — example live job: it logs in with the masked CI variables
  `EPI_USERNAME` / `EPI_PASSWORD` (Settings → CI/CD → Variables, "Masked" +
  "Protected") and publishes `papers.json` as an artifact. The token exists
  only for the duration of the job, so there is nothing to renew by hand.

## Tests

```sh
poetry install --with dev
pytest
```

The test suite is fully offline: every HTTP exchange is mocked
(`requests-mock`) and token files are redirected to a temporary directory.

## Note on credentials

Token files (`token.json`, `auth.json`) are gitignored and must never be
committed. If real credentials ever end up in a commit or get shared,
revoke or rotate your Episciences API password.
