from __future__ import annotations

import contextlib
import re
from typing import Optional

from django.conf import settings

from documentation.mcp_server.auth import BearerTokenMiddleware, current_token_pk
from documentation.mcp_server.scoping import ScopedDocumentation, scope_for
from documentation.models import MCPToken
from documentation.services.markdown import slugify
from documentation.services.search import parse_frontmatter

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _ServerClass
except ModuleNotFoundError:  # mcp < 2
    from mcp.server.fastmcp import FastMCP as _ServerClass


DEFAULT_MAX_CONTENT_CHARS = 40000
CONTENT_FORMATS = ("markdown", "html")
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def create_server(name: str | None = None):
    return _ServerClass(name or "Enezadocs")


mcp = create_server()


def _scoped() -> ScopedDocumentation:
    pk = current_token_pk()
    if pk is None:
        raise RuntimeError("Unauthenticated MCP request.")
    token = (
        MCPToken.objects.select_related(
            "server",
            "server__site",
            "server__section",
            "server__group",
        )
        .filter(
            pk=pk,
            enabled=True,
            server__enabled=True,
            server__site__enabled=True,
        )
        .first()
    )
    if token is None:
        raise RuntimeError("Invalid or disabled MCP token.")
    return ScopedDocumentation(scope_for(token))


def _default_max_chars() -> int:
    try:
        value = int(getattr(settings, "MCP_MAX_CONTENT_CHARS", DEFAULT_MAX_CONTENT_CHARS))
    except (TypeError, ValueError):
        return DEFAULT_MAX_CONTENT_CHARS
    return value if value > 0 else DEFAULT_MAX_CONTENT_CHARS


def _resolve_limit(max_chars: int) -> Optional[int]:
    """Return the character cap, or ``None`` for no limit.

    ``0`` uses the configured default; a negative value means unlimited.
    """
    if max_chars is None or max_chars == 0:
        return _default_max_chars()
    if max_chars < 0:
        return None
    return max_chars


def _pick_text(document, content_format: str) -> str:
    if content_format == "html":
        return document.html or ""
    return document.content or ""


def _paginate(text: str, offset: int, limit: Optional[int]) -> dict:
    total = len(text)
    start = max(int(offset or 0), 0)
    if start > total:
        start = total
    end = total if limit is None else min(start + limit, total)
    chunk = text[start:end]
    next_offset = end if end < total else None
    return {
        "content": chunk,
        "content_offset": start,
        "content_returned": len(chunk),
        "content_total": total,
        "next_offset": next_offset,
        "truncated": next_offset is not None,
    }


def _metadata(document) -> dict:
    return {
        "title": document.title,
        "path": document.path,
        "description": document.description,
        "headings": document.headings,
        "breadcrumbs": document.breadcrumbs,
        "previous": document.previous,
        "next": document.next,
        "source_url": document.source_url,
        "hidden": document.hidden,
        "draft": document.draft,
    }


def _load(path: str):
    document = _scoped().document(path)
    if document is None:
        raise ValueError(f"Document not found or out of scope: {path}")
    return document


def _outline(body: str):
    """Return the body lines and the markdown headings with stable slugs."""
    lines = body.split("\n")
    headings = []
    used: dict[str, int] = {}
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _MD_HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        text = match.group(2).strip()
        base = slugify(text, "-") or "section"
        count = used.get(base, 0)
        used[base] = count + 1
        heading_id = base if count == 0 else f"{base}_{count}"
        headings.append({"level": level, "id": heading_id, "text": text, "line": index})
    return lines, headings


def _section_markdown(lines: list[str], headings: list[dict], index: int) -> str:
    start = headings[index]["line"]
    level = headings[index]["level"]
    end = len(lines)
    for following in headings[index + 1:]:
        if following["level"] <= level:
            end = following["line"]
            break
    return "\n".join(lines[start:end]).strip("\n")


def _match_heading(headings: list[dict], heading: str):
    key = (heading or "").strip()
    if not key:
        return None
    key_lower = key.lower()
    key_slug = slugify(key, "-")
    for position, item in enumerate(headings):
        if (
            item["id"] == key
            or item["id"] == key_slug
            or item["text"].lower() == key_lower
        ):
            return position
    for position, item in enumerate(headings):
        if key_lower in item["text"].lower() or (key_slug and key_slug in item["id"]):
            return position
    return None


@mcp.tool()
def get_scope() -> dict:
    """Return the site, section, and group this MCP token can read."""
    return _scoped().get_scope_dict()


@mcp.tool()
def get_navigation() -> list:
    """Return the documentation navigation tree within this token's scope."""
    return [node.to_dict() for node in _scoped().tree()]


@mcp.tool()
def search_docs(query: str, limit: int = 20) -> list:
    """Search documentation within this token's scope."""
    return _scoped().search(query, limit=limit)


@mcp.tool()
def get_document(
    path: str,
    format: str = "markdown",
    offset: int = 0,
    max_chars: int = 0,
) -> dict:
    """Read one documentation page inside this token's scope.

    Returns the markdown body by default (``format="markdown"``); pass
    ``format="html"`` for rendered HTML. Long pages are paginated: when the
    result has ``truncated=true``, call this tool again with ``next_offset``
    to fetch the remainder. ``max_chars`` caps the returned characters (``0``
    uses the server default, a negative value returns the whole body).
    """
    content_format = (format or "markdown").strip().lower()
    if content_format not in CONTENT_FORMATS:
        raise ValueError(
            f"Unsupported format '{format}'. Use one of: {', '.join(CONTENT_FORMATS)}."
        )
    document = _load(path)
    limit = _resolve_limit(max_chars)
    payload = _metadata(document)
    payload.update(
        {
            "content_format": content_format,
            **_paginate(_pick_text(document, content_format), offset, limit),
        },
    )
    return payload


@mcp.tool()
def get_document_meta(path: str) -> dict:
    """Return a document's metadata and outline without its body.

    Use this first to inspect headings, neighbours, and sizes, then fetch only
    the part you need with ``get_document`` or ``get_document_section``.
    """
    document = _load(path)
    payload = _metadata(document)
    payload.update(
        {
            "content_length": len(document.content or ""),
            "html_length": len(document.html or ""),
        },
    )
    return payload


@mcp.tool()
def get_document_section(
    path: str,
    heading: str,
    offset: int = 0,
    max_chars: int = 0,
) -> dict:
    """Read a single markdown section of a page.

    ``heading`` matches a heading's ``id`` (from ``headings``) or its text,
    case-insensitively; a partial match is accepted. The section runs from that
    heading up to the next heading of the same or higher level. Use this to
    read one part of a long page without pulling the whole document.
    """
    document = _load(path)
    _, body = parse_frontmatter(document.content or "")
    lines, headings = _outline(body)
    index = _match_heading(headings, heading)
    if index is None:
        available = ", ".join(item["text"] for item in headings) or "none"
        raise ValueError(
            f"Heading '{heading}' not found in {path}. Available headings: {available}."
        )
    matched = headings[index]
    section = _section_markdown(lines, headings, index)
    limit = _resolve_limit(max_chars)
    payload = _metadata(document)
    payload.update(
        {
            "heading": {
                "level": matched["level"],
                "id": matched["id"],
                "text": matched["text"],
            },
            "content_format": "markdown",
            **_paginate(section, offset, limit),
        },
    )
    return payload


def _register_resources(server) -> None:
    try:

        @server.resource("docs://{path}")
        def read_document(path: str) -> str:
            """Read a documentation page inside this token's scope."""
            document = _scoped().document(path)
            if document is None:
                raise ValueError(f"Document not found or out of scope: {path}")
            return document.content

    except Exception:
        # Older/newer SDKs may not support this resource template; the tools
        # above remain the supported surface.
        return


_register_resources(mcp)


def _transport_security():
    """Build MCP transport-security settings from Django's ``ALLOWED_HOSTS``.

    The MCP endpoint is served by Starlette, not Django, so Django's
    ``ALLOWED_HOSTS`` validation never applies to it. The MCP SDK instead
    auto-enables DNS rebinding protection restricted to localhost when the
    ``host`` argument is left at its default, which rejects every production
    request whose Host header is the public domain (HTTP 421). Derive the
    allowed hosts from ``ALLOWED_HOSTS`` so the endpoint accepts the same
    hosts as the rest of the site.
    """
    try:
        from mcp.server.transport_security import TransportSecuritySettings
    except ImportError:
        return None
    allowed = []
    for entry in getattr(settings, "ALLOWED_HOSTS", []):
        host = (entry or "").strip().lstrip(".")
        if not host or host == "*":
            continue
        allowed.append(host)
        allowed.append(f"{host}:*")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(allowed),
        allowed_hosts=allowed,
    )


def _streamable_http_app():
    """Build the ASGI app for the MCP endpoint.

    Stateless HTTP keeps every request self-contained so the token context set
    by the bearer middleware reliably reaches the tool handler. Older SDK
    builds without ``stateless_http`` fall back to the default mode.
    """
    transport_security = _transport_security()
    for kwargs in (
        {
            "streamable_http_path": "/",
            "stateless_http": True,
            "transport_security": transport_security,
        },
        {"streamable_http_path": "/", "transport_security": transport_security},
        {"streamable_http_path": "/", "stateless_http": True},
        {"streamable_http_path": "/"},
    ):
        try:
            return mcp.streamable_http_app(**kwargs)
        except TypeError:
            continue
    return mcp.streamable_http_app()


def build_asgi_app(django_app):
    """Wrap the Django ASGI app with the MCP endpoint at ``MCP_PATH``."""
    from starlette.applications import Starlette
    from starlette.routing import Mount

    prefix = settings.MCP_PATH or "/mcp"
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    prefix = prefix.rstrip("/") or "/mcp"

    mcp_app = BearerTokenMiddleware(_streamable_http_app())

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    return Starlette(
        routes=[
            Mount(prefix, app=mcp_app),
            Mount("/", app=django_app),
        ],
        lifespan=lifespan,
    )
