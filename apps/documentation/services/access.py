from __future__ import annotations

import dataclasses

import frontmatter

PUBLIC = "public"
PRIVATE = "private"

_ACCESS_KEYS = ("access",)


def normalize(value) -> str:
    """Normalize a raw frontmatter value to PUBLIC or PRIVATE."""
    if value is None:
        return PUBLIC
    text = str(value).strip().lower()
    if text in ("private", "true", "1", "yes", "restricted"):
        return PRIVATE
    return PUBLIC


def meta_access(metadata: dict) -> str:
    """Read the access level from parsed frontmatter metadata."""
    for key in _ACCESS_KEYS:
        if key in metadata:
            return normalize(metadata[key])
    return PUBLIC


def raw_access(raw: str | None) -> str:
    """Parse a raw markdown document and return its access level."""
    if not raw:
        return PUBLIC
    try:
        post = frontmatter.loads(raw)
        return meta_access(dict(post.metadata or {}))
    except Exception:
        return PUBLIC


def filter_public_documents(nodes: list, is_private) -> list:
    """Return a NEW navigation tree without private content.

    ``is_private(node)`` must return True for documents that anonymous users
    may not see. A private document that also carries children is dropped
    together with its whole subtree. Folder nodes whose children are all
    filtered out are dropped as well. Input nodes are never mutated.
    """
    out: list = []
    for node in nodes:
        if node.type == "document":
            if node.children:
                if is_private(node):
                    continue
                children = filter_public_documents(node.children, is_private)
                if children:
                    out.append(dataclasses.replace(node, children=children))
                continue
            if not is_private(node):
                out.append(node)
        else:
            children = filter_public_documents(node.children, is_private)
            if children:
                out.append(dataclasses.replace(node, children=children))
    return out
