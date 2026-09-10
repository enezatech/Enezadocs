from __future__ import annotations

import contextvars

from asgiref.sync import sync_to_async

_current_token_pk: contextvars.ContextVar = contextvars.ContextVar(
    "mcp_token_pk",
    default=None,
)


def current_token_pk():
    """Return the PK of the token authenticated for the current request."""
    return _current_token_pk.get()


def _bearer_token(scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name.lower() == b"authorization":
            text = value.decode("latin-1")
            if text.lower().startswith("bearer "):
                return text[7:].strip()
    return None


def _server_slug(scope) -> str:
    """Return the first path segment, which identifies the MCP server.

    Starlette's ``Mount`` keeps ``scope["path"]`` absolute and only records the
    prefix in ``root_path`` (routing matches on ``path`` minus ``root_path``).
    Strip ``root_path`` so the slug is read after the mount prefix rather than
    the prefix itself.
    """
    path = scope.get("path", "") or ""
    root_path = scope.get("root_path", "") or ""
    if root_path and path.startswith(root_path):
        path = path[len(root_path):]
    for segment in path.split("/"):
        if segment:
            return segment
    return ""


def _lookup_server(slug):
    from documentation.models import MCPServer

    return (
        MCPServer.objects.filter(
            slug=slug,
            enabled=True,
            site__enabled=True,
        )
        .select_related("site", "section", "group")
        .first()
    )


async def _send_error(send, status: int, message: str) -> None:
    body = message.encode("utf-8")
    headers = [
        (b"content-type", b"text/plain; charset=utf-8"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if status == 401:
        headers.append((b"www-authenticate", b"Bearer"))
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": headers,
        },
    )
    await send({"type": "http.response.body", "body": body})


class BearerTokenMiddleware:
    """ASGI middleware that authenticates and routes an MCP request.

    The first path segment selects an ``MCPServer`` (``<base>/<slug>/``). The
    bearer token must belong to that server. Valid requests have their path
    rewritten to ``/`` so the MCP app handles them, and the token is exposed to
    tool handlers through a context variable.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        slug = _server_slug(scope)
        if not slug:
            await _send_error(
                send,
                404,
                "Specify an MCP server in the path, for example <base>/<server-slug>/.",
            )
            return

        raw = _bearer_token(scope)
        if not raw:
            await _send_error(send, 401, "Invalid or missing bearer token.")
            return

        from documentation.services.mcp_tokens import resolve_token

        token = await sync_to_async(resolve_token)(raw)
        if token is None:
            await _send_error(send, 401, "Invalid or missing bearer token.")
            return

        server = await sync_to_async(_lookup_server)(slug)
        if server is None:
            await _send_error(send, 404, "Unknown MCP server.")
            return
        if token.server_id != server.pk:
            await _send_error(send, 401, "Invalid or missing bearer token.")
            return

        new_scope = dict(scope)
        new_scope["path"] = "/"
        new_scope["root_path"] = scope.get("root_path", "") + "/" + slug
        reset = _current_token_pk.set(token.pk)
        try:
            await self.app(new_scope, receive, send)
        finally:
            _current_token_pk.reset(reset)
