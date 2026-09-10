---
menu name: MCP Server Setup
position: 4
---

# MCP Server Setup

This guide shows how to publish one or more documentation MCP servers and connect an AI
agent to them.

The app exposes documentation over the
[Model Context Protocol](https://modelcontextprotocol.io) (MCP) so an agent can list the
navigation, search, and read pages. Servers are **database-backed**: each one has its own
scope (a site, with an optional section and group) and its own endpoint URL. You can run
several specialized servers from the same app, for example one per product area or audience.

---

## 1. Before you start

You need:

- The project checked out and its dependencies installed.
- At least one **enabled** documentation site with imported navigation
  (Sections/Groups come from **Import navigation structure from provider**).
- An ASGI server to serve the app (MCP cannot run under `runserver`/WSGI).

Install dependencies (includes `mcp` and `uvicorn`):

```bash
pip install -r requirements.txt
```

Apply the database migrations that create the server and token tables:

```bash
python manage.py migrate
```

---

## 2. Configure and run

Only the global endpoint settings live in configuration; the servers themselves are in the
database.

| Setting | Environment variable | Default | Purpose |
| --- | --- | --- | --- |
| Endpoint on/off | `MCP_ENABLED` | `1` (on) | Set to `0` to disable all MCP endpoints. |
| Base path | `MCP_PATH` | `/mcp` | Prefix for every server endpoint. |

Each server is addressed at the base path plus its slug, for example `/mcp/developer/` or
`/mcp/billing/`.

Start the site and all MCP endpoints together on one port:

```bash
python manage.py run_mcp
```

This serves `http://127.0.0.1:8000`. Pass a custom bind if needed:

```bash
python manage.py run_mcp 0.0.0.0:9000
```

`run_mcp` is a thin wrapper around `uvicorn config.asgi:application --reload`, so admin and
static files work in development. Auto-reload can be turned off with `--no-reload`. You can
also run uvicorn directly in production:

```bash
python -m uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

> The web app keeps working at `/`. `python manage.py runserver` will **not** serve the MCP
> endpoints; use `run_mcp` or an ASGI server such as `uvicorn`/`hypercorn`.

In production, put the app behind TLS (for example with a reverse proxy) so tokens are never
sent over plain HTTP.

---

## 3. Create a server (scope)

A server defines what its agents can read:

- **Site** (required) — the documentation site.
- **Section** (optional) — a top-level section node.
- **Group** (optional) — a group node inside that section.

Scope rules:

| Section | Group | The server can read |
| --- | --- | --- |
| — | — | The whole site. |
| set | — | That section and everything below it. |
| set | set | Only that group (the group must live inside the section). |

In the Django admin:

1. Open **MCP servers → Add**.
2. Give it a **name** and a **slug** (the URL segment, e.g. `developer`).
3. Choose the **site**, and optionally a **section** and **group**.
4. Save. The server is now live at `<base>/<slug>/` while **enabled** is ticked.

You can create as many servers as you need; each has an independent scope and endpoint.
Disabling a server takes its endpoint offline without affecting the others.

---

## 4. Issue a token

Every request must send `Authorization: Bearer <token>`. A token belongs to exactly one
server and is only accepted at that server's endpoint; it inherits the server's scope. The
per-token **allow private** flag controls whether it may read content marked
`access: private`.

### Option A — Django admin

1. Open **MCP tokens → Add**.
2. Fill in a **name**, choose the **server**, and optionally tick **allow private**.
3. Save. The bearer token is shown at the top of the page, and again on the token's change
   page with a **Copy** button, so you can retrieve it later.

To re-copy tokens, open **MCP tokens**, select one or more rows, and choose **Reveal bearer
token**. To issue a fresh value instead (which invalidates the old one), use **Regenerate
bearer token**. Tokens created before the encrypted copy was added have no stored value;
regenerate them to get a copyable token.

Disable a token at any time by clearing **enabled**, and check **last used at** to see
whether an agent is still calling it.

### Option B — Management command

```bash
# Issue a token for an existing server
python manage.py create_mcp_token --name "Docs agent" --server developer

# Create the server (if missing) and issue a token in one step
python manage.py create_mcp_token --name "Changes agent" --server developer \
    --site <site-slug> --section "Developer" --group "Changes" --allow-private
```

`--server` is the server slug. `--site`, `--section`, and `--group` are only used when the
server is created; `--section`/`--group` accept a node **id** or **title**. The command
prints the token once; store it in your agent's secret configuration.

---

## 5. Connect an agent

Use the base URL of your deployment plus `/mcp/<server-slug>/` and the token:

```
https://docs.example.com/mcp/developer/
Authorization: Bearer mcp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### Kilo

Add a remote MCP server to `kilo.json` (project) or `~/.config/kilo/kilo.json` (global):

```jsonc
{
  "mcp": {
    "enezadocs-developer": {
      "type": "remote",
      "url": "https://docs.example.com/mcp/developer/",
      "headers": { "Authorization": "Bearer mcp_XXXXXXXX" },
      "enabled": true
    }
  }
}
```

### VS Code

Create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "enezadocs-developer": {
      "type": "http",
      "url": "https://docs.example.com/mcp/developer/",
      "headers": { "Authorization": "Bearer mcp_XXXXXXXX" }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "enezadocs-developer": {
      "url": "https://docs.example.com/mcp/developer/",
      "headers": { "Authorization": "Bearer mcp_XXXXXXXX" }
    }
  }
}
```

### Claude Desktop and other clients

Clients that only speak stdio can bridge to a remote HTTP server. For example, using the
`mcp-remote` bridge:

```json
{
  "mcpServers": {
    "enezadocs-developer": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://docs.example.com/mcp/developer/",
        "--header",
        "Authorization: Bearer mcp_XXXXXXXX"
      ]
    }
  }
}
```

Add one entry per server you want the agent to use. Check your client's documentation for the
exact configuration keys, since these vary between versions.

---

## 6. What the agent can do

Once connected, the agent has these read-only tools:

| Tool | What it returns |
| --- | --- |
| `get_scope` | The server and the site/section/group the token can read. |
| `get_navigation` | The navigation tree inside the server's scope. |
| `search_docs` | Full-text search restricted to the scope. |
| `get_document` | One page by path: title, headings, markdown content, and rendered HTML. |

Each page is also available as a resource at `docs://<path>`. Every operation is checked
against the server's scope, so an agent cannot list, search, or read anything outside it.

---

## 7. Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `401 Invalid or missing bearer token` | Header missing or malformed, token disabled, or the token belongs to a different server. Check the `Authorization: Bearer <token>` header and that the token was issued for this server's slug. |
| `404` at the endpoint | The server slug is wrong or the server is disabled; or `MCP_ENABLED=0`; or the app is being served by WSGI/`runserver`. Start it with `python manage.py run_mcp`. |
| `404 Specify an MCP server` at the base path | The URL needs a server slug, e.g. `/mcp/developer/`. |
| Tools return nothing | The server's section/group has no pages, or the content is private and `allow_private` is off. Verify with `get_scope` and `get_navigation`. |
| Empty after re-importing structure | **Import navigation structure** recreates nodes, so a server's `section`/`group` links are cleared and it falls back to the whole site. Re-select the section/group after a rebuild. |

---

## 8. Security notes

- Treat a token like a password. Anyone with it can read everything inside its server's scope.
- Prefer the narrowest scope: scope a server to a group or section instead of a whole site.
- Issue one token per client/server pair so you can revoke independently.
- Leave **allow private** off unless the agent genuinely needs private content.
- Revoke a token immediately by clearing **enabled** in the admin.
- Serve the endpoints over HTTPS; disable them all with `MCP_ENABLED=0` if unused.

For implementation details, see the developer note **MCP Documentation Server**.
