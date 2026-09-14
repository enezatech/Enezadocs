# Planure: Admin "Copy MCP Setup" (Kilo client config)

Status: **Planned**

## Feature Overview

Let an admin copy a ready-to-paste client setup for an MCP server directly from the Django
admin, instead of hand-assembling a `kilo.json` snippet. The change page of an `MCPToken`
already re-reveals the raw bearer token with a Copy button; this feature adds a second
read-only field that renders the **complete** Kilo configuration as pretty JSON with its own
Copy button.

Success criteria (user-verified): on an `MCPToken` change page with a stored token, the admin
sees a `kilo.json` block whose `url` matches `<base>/mcp/<slug>/` for the token's server and
whose `Authorization` header contains `Bearer <raw token>`; the Copy button places the exact
JSON on the clipboard; pasting it into `kilo.json` lets a Kilo client connect to the server.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Where shown | `MCPToken` change page only (has the raw token + server link). |
| Base URL source | Derived from the admin request via `request.build_absolute_uri("/")` (trailing slash stripped). |
| URL shape | `<base>/<MCP_PATH>/<server.slug>/` (reuses `settings.MCP_PATH`, default `/mcp`). |
| Snippet key | `"<site.slug>-<server.slug>"` (e.g. `enezadocs-developer`), matching the existing docs examples. |
| Client format | Kilo `kilo.json` only (`{"mcp": {...}}` with `type: remote`, `url`, `headers`, `enabled`). |
| Token source | `MCPToken.token` (encrypted raw copy). Blank token → show "not stored" hint instead of JSON. |
| Copy mechanism | Read-only `<textarea>` + a Copy button using `navigator.clipboard` (same pattern as `token_value`). |
| Migration | None — no new/removed model fields. |

## Components & modules involved

**Files changed**
- `apps/documentation/services/mcp_tokens.py` — add `build_client_config(token, base_url)`
  helper (needs `from django.conf import settings`).
- `apps/documentation/admin.py` — `MCPTokenAdmin`: stash `request` in `changeform_view`, add a
  `client_setup` read-only display method + Copy button, register it in `readonly_fields`.

**No changes**
- Models, migrations, settings, URLs, ASGI wiring, templates, and the MCP server itself.

## Implementation steps

1. **Config builder** — in `apps/documentation/services/mcp_tokens.py`, add
   `build_client_config(token, base_url: str) -> dict` returning
   `{"mcp": {f"{token.server.site.slug}-{token.server.slug}": {"type": "remote",
   "url": f"{base_url.rstrip('/')}/{MCP_PATH}/{token.server.slug}/",
   "headers": {"Authorization": f"Bearer {token.token}"}, "enabled": True}}}`.
   Derive `MCP_PATH` from `settings.MCP_PATH` (default `/mcp`, strip slashes). Import
   `from django.conf import settings`.
2. **Admin request access** — in `MCPTokenAdmin`, override
   `changeform_view(self, request, object_id=None, form_url="", extra_context=None)` to store
   `self._request = request` before calling `super()`. (Django readonly display methods receive
   only `obj`, so the request must be stashed on the instance.)
3. **Copy field** — add `@admin.display(description="Kilo client setup (kilo.json)")` method
   `client_setup(self, obj)` that: returns "Save the token first." when `obj.pk` is unset;
   returns a `mark_safe` "Not stored — Regenerate bearer token." hint when `obj.token` is blank;
   otherwise builds `json.dumps(build_client_config(obj, base), indent=2)` where `base` is
   `self._request.build_absolute_uri("/").rstrip("/")` (or `""` when `_request` is absent).
   Render it via `format_html` into a read-only `<textarea>` (monospace, full width, ~9 rows)
   plus a Copy `<button>` that copies the textarea value by id
   (`document.getElementById(...).value`), keeping the two adjacent. Add `"client_setup"` to
   `readonly_fields`. Add `import json` at the top of `admin.py`.
4. **Docs** — update `docs/Documention/Get Started/mcp-server-setup.md` (Kilo section, step 4
   Option A) to mention the new "Kilo client setup" copy field.

## Validation (user-run — agent does not test)

1. `python manage.py migrate` (no changes expected); start `python manage.py run_mcp`.
2. Open a token with a stored value (create or Regenerate one). Confirm the new field shows
   JSON whose `url` is `<current-admin-origin>/mcp/<slug>/` and whose token matches the
   existing "Bearer token" field.
3. Click **Copy** and paste into a `kilo.json`; confirm the Kilo client connects
   (`get_scope` returns the expected server/site).
4. Open a token whose raw value is not stored (pre-migration token) and confirm the field shows
   the "not stored — regenerate" hint, not broken JSON.
5. Verify no other admin pages or the MCP endpoint regress (token reveal/regenerate still work).

## Risks / notes

- **Host correctness** — base URL follows the admin request's Host header. Behind a reverse
  proxy that forwards the public `Host`, this is correct; an admin on `127.0.0.1:8000` gets a
  localhost URL (acceptable for local dev). If a fixed public origin is later needed, add an
  `MCP_PUBLIC_BASE_URL` setting (out of scope now).
- **`previousElementSibling` fragility** — avoided by targeting the textarea by id.
- **Formatting** — `format_html` escapes the JSON, which decodes correctly inside `<textarea>`.
- **Single format** — VS Code / Cursor / mcp-remote snippets are out of scope; the helper dict
  shape is intentionally easy to extend later.
- Model edits (if any later) must follow the repo field convention (own line, `verbose_name`,
  aligned closing paren) — none are required here.

## Out of scope

- Config snippets for VS Code, Cursor, or stdio/mcp-remote bridges.
- Surfacing the snippet on the `MCPServer` change page (the token inline already links through).
- A configurable/`MCP_PUBLIC_BASE_URL` setting.
- Agent-run testing.
