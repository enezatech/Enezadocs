# Planure: MCP Documentation Server (database-backed, scoped)

> Status: **Implemented**. The authoritative planure lives at
> `feature_Planure/feature_Planure_mcp_documentation_server.md`; this page mirrors it for
> the documentation site.

## Feature Overview

Expose this documentation app to AI agents through **Model Context Protocol (MCP)**
servers served over **Streamable HTTP** from the Django ASGI app. Servers are defined in the
database, so one app can publish several specialized servers, each with its own scope and
endpoint.

Scope model: each `MCPServer` is bound to **one `DocumentationSite`**, with an **optional
`section` node** and an **optional `group` node** inside it. Empty section = whole site; empty
group = whole section. Agents authenticate with a **bearer token that belongs to one server**
and can only read documentation inside that server's scope. A token may optionally read
private content via an explicit `allow_private` flag.

Success criteria (user-verified): an agent with a valid token can discover the scoped
navigation, search, and read page content (markdown + rendered HTML); a server scoped to a
section/group cannot read, search, or list anything outside that subtree; invalid, disabled,
mismatched-server, or out-of-scope access is rejected; private content is only reachable when
the token sets `allow_private`.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Protocol / transport | MCP over **Streamable HTTP** from the Django ASGI app. |
| Hosting | Mount the MCP ASGI app next to Django in `config/asgi.py`; run under an ASGI server. |
| Run command | `python manage.py run_mcp [host:port]` serves the site and all MCP endpoints together (uvicorn); equivalent to `uvicorn config.asgi:application`. |
| Server model | `MCPServer`: name, slug, description, site, optional section/group, enabled. Owns the scope and the endpoint. |
| Endpoint | `<MCP_PATH>/<server-slug>/` (e.g. `/mcp/developer/`); bare base path returns 404. |
| Credential model | `MCPToken` belongs to one `MCPServer`; scope is inherited from the server. |
| Token storage | SHA-256 hash for authentication + an encrypted copy of the raw value so an admin can re-copy it; short display prefix. |
| Token format | `mcp_` + `secrets.token_urlsafe(32)`; `prefix = raw[:12]`. |
| Token auth | `Authorization: Bearer <token>` verified by custom ASGI middleware. |
| Private content | Per-token `allow_private` boolean (default `False`). |
| MCP surface | Read-only tools `get_scope`, `get_navigation`, `search_docs`, `get_document`; pages exposed as `docs://<path>` resources. |
| Enforcement | Tree, search, document read, and resource read intersect the server's allowed path set. |
| Disabled | Disabled token, server, or site is rejected (401); unknown server slug is 404. |
| Out-of-scope read | Tool error; never leak content or existence. |
| Stateless HTTP | Endpoint built with `stateless_http=True` (fallback for older SDKs) so the bearer context reaches tool handlers. |

## Scope semantics

- `DocumentationNode.path` is the folder path relative to the provider root.
- Effective prefix: `group.path` if set, else `section.path` if set, else `""` (whole site).
- A page is in scope when `prefix == ""`, `path == prefix`, or `path.startswith(prefix + "/")`.
- If both section and group are set, the group must be below the section and same-site.
- Section must be `type=section`; group must be `type=group`; both same-site as the server.
- `allow_private=False` builds the public tree then filters by prefix (a private scope is empty).
- `allow_private=True` builds the full tree and passes the explicit scoped `allowed_paths`
  to `query_documents`, so search cannot escape the scope.
- A selected section/group with a blank `path` is rejected (`MCPServer.clean()`), fail-closed.

## Components & modules involved

**New files**
- `apps/documentation/mcp_server/__init__.py`
- `apps/documentation/mcp_server/server.py` — MCP instance, tools, resource, ASGI app builder.
- `apps/documentation/mcp_server/auth.py` — server-slug routing, bearer auth, token contextvar.
- `apps/documentation/mcp_server/scoping.py` — `Scope`, `scope_for`, `filter_tree`, `ScopedDocumentation`.
- `apps/documentation/services/mcp_tokens.py` — `generate_token`, `hash_token`, `resolve_token`.
- `apps/documentation/management/commands/create_mcp_token.py` — CLI issuance.
- `apps/documentation/management/commands/run_mcp.py` — run site + MCP on one ASGI server.
- `apps/documentation/migrations/0007_mcptoken.py` — initial token table.
- `apps/documentation/migrations/0008_mcpserver.py` — `MCPServer` + `MCPToken.server`, converting existing tokens.
- `apps/documentation/migrations/0009_mcptoken_token_alter_mcptoken_token_hash.py` — encrypted raw token copy for admin re-copy.

**Files changed**
- `apps/documentation/models.py` — `MCPServer` + `MCPToken` (server FK) + validation.
- `apps/documentation/admin.py` — `MCPServerAdmin` (+ read-only token inline) and `MCPTokenAdmin`.
- `config/settings.py` — `MCP_ENABLED`, `MCP_PATH`.
- `config/asgi.py` — mount MCP; `ASGIStaticFilesHandler` in DEBUG.
- `requirements.txt` — `mcp>=1.8`, `uvicorn[standard]>=0.30`.
- `docs/Developer/mcp-documentation-server.md`, `docs/Documention/Get Started/mcp-server-setup.md`.

## Implementation steps

1. **Dependencies + settings** — add `mcp` and `uvicorn[standard]`; add `MCP_ENABLED` and
   `MCP_PATH`. No per-server settings.
2. **Models** — add `MCPServer` (name, slug, description, site, optional section/group,
   enabled, timestamps) with `clean()` validating node type, same-site, ancestry, and
   non-blank path; give `MCPToken` a required `server` FK; migrations `0007_mcptoken`,
   `0008_mcpserver`.
3. **Token service** — generate/hash/resolve; `resolve_token` selects the server and rejects
   disabled tokens/servers/sites and throttles `last_used_at` writes.
4. **Scoping** — `Scope(server, site, section, group, allow_private, prefix)`, `scope_for(token)`,
   non-mutating `filter_tree`, and `ScopedDocumentation` (`paths`, `tree`, `search`, `document`,
   `get_scope_dict` including the server).
5. **Auth middleware** — resolve the first path segment to an `MCPServer`, require the bearer
   token to belong to it (unknown/disabled server → 404, token/server mismatch → 401), rewrite
   the path for the MCP app, and set the request contextvar.
6. **MCP server** — tools `get_scope`, `get_navigation`, `search_docs`, `get_document`; a
   `docs://{path}` resource; `MCPServer`/`FastMCP` compatibility; stateless streamable app.
7. **ASGI wiring** — `config/asgi.py` mounts MCP at `MCP_PATH` when enabled and serves static
   in DEBUG.
8. **Admin** — `MCPServerAdmin` (scope + read-only token inline) and `MCPTokenAdmin` (server
   picker, shown-once issuance).
9. **CLI** — `create_mcp_token` (`--server`, and `--site`/`--section`/`--group` to create a
   missing server) and `run_mcp`.
10. **Docs** — developer note + user setup guide.

## As-built notes

- **Migration `0008_mcpserver`** converts every pre-existing token into its own `MCPServer`
  (preserving its site/section/group) before dropping the old columns.
- **Static files under ASGI** — `config/asgi.py` wraps Django with `ASGIStaticFilesHandler`
  when `DEBUG`, so admin/static assets work under uvicorn.
- **SDK compatibility** — imports `mcp.server.mcpserver.MCPServer` (mcp >= 2) and falls back to
  `mcp.server.fastmcp.FastMCP` (mcp < 2); `stateless_http` has a fallback for older builds.
- **Slug routing under a mount** — Starlette's `Mount` leaves `scope["path"]` absolute and only
  sets `root_path`; `BearerTokenMiddleware._server_slug` strips `root_path` before reading the
  slug, otherwise `<MCP_PATH>/<slug>/` resolved the prefix (`mcp`) as the slug and returned 404.
- **Fails closed on blank paths** — `MCPServer.clean()` rejects a selected section/group whose
  `path` is empty.
- **Admin re-copy** — `MCPToken.token` stores an encrypted copy of the raw value; the change
  page shows the token with a Copy button, and the changelist offers **Reveal bearer token**
  and **Regenerate bearer token**. Tokens created earlier show "Not stored" until regenerated.
- **Manual step retained** — `migrate` and running the server are user actions; the agent does
  not test.

## Validation (user-run — agent does not test)

1. `pip install -r requirements.txt`; `python manage.py migrate` (applies `0008_mcpserver`).
2. Create an `MCPServer` (admin) or `create_mcp_token --server <slug> --site <site>`, and note
   the raw token once.
3. `python manage.py run_mcp`; confirm the MCP client initializes at `/mcp/<slug>/` with the
   bearer token and that `/`, `/docs/...`, `/admin/` still work.
4. `get_scope` reports the server and site/section/group; `get_navigation` contains only the
   scoped subtree.
5. `search_docs`/`get_document`/resource reads succeed inside scope and fail (no content, no
   existence leak) for a sibling section/group, another server, and an unknown path.
6. `allow_private=False` cannot read private content; `allow_private=True` can, in scope only.
7. Disabled token/server/site or a token used against another server → 401; unknown server
   slug → 404.

## Risks / notes

- **ASGI required**; `runserver`/WSGI does not serve MCP.
- **SDK API drift**: `MCPServer` vs `FastMCP`; `stateless_http` may be unavailable in older builds (fallback).
- **Contextvar propagation** relies on stateless HTTP; fallback is resolving the token per handler.
- **Search scoping**: the scoped layer always passes explicit `allowed_paths`.
- **Structure re-import** clears a server's `section`/`group` links (`SET_NULL`) → re-verify scope.
- **No binary assets** served over MCP.
- Model edits follow the repo field convention (own line, `verbose_name`, aligned closing paren).

## Out of scope

- Write tools / editing docs via MCP.
- OAuth 2.1 authorization-server flow.
- Multiple scopes per server; per-user Django-group permissions.
- Rate limiting/quotas and audit logging beyond `last_used_at`.
- Binary asset/image serving through MCP.
- Agent-run testing.
