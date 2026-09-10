from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

TOKEN_SCHEME = "mcp_"
TOKEN_PREFIX_LENGTH = 12
LAST_USED_THROTTLE = timedelta(seconds=60)


def generate_token() -> tuple[str, str]:
    """Return a new ``(raw, prefix)`` token pair.

    Only the prefix is safe to display again; the raw value is shown once at
    creation time and is never persisted.
    """
    raw = f"{TOKEN_SCHEME}{secrets.token_urlsafe(32)}"
    return raw, raw[:TOKEN_PREFIX_LENGTH]


def hash_token(raw: str) -> str:
    """Return the SHA-256 hex digest used to store an MCP token."""
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def resolve_token(raw: str):
    """Return the enabled :class:`MCPToken` for ``raw`` or ``None``.

    Tokens attached to disabled sites are rejected. ``last_used_at`` is
    refreshed at most once per minute to avoid a write on every request.
    """
    if not raw or not raw.strip():
        return None

    from documentation.models import MCPToken

    token = (
        MCPToken.objects.select_related(
            "server",
            "server__site",
            "server__section",
            "server__group",
        )
        .filter(
            token_hash=hash_token(raw.strip()),
            enabled=True,
            server__enabled=True,
            server__site__enabled=True,
        )
        .first()
    )
    if token is None:
        return None

    now = timezone.now()
    if token.last_used_at is None or now - token.last_used_at > LAST_USED_THROTTLE:
        token.last_used_at = now
        token.save(update_fields=["last_used_at"])
    return token
