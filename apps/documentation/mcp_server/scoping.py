from __future__ import annotations

import dataclasses
from typing import Optional

from documentation.services.base import NavigationNode
from documentation.services.documentation import DocumentationService
from documentation.services.navigation import flatten
from documentation.services.search import query_documents


@dataclasses.dataclass
class Scope:
    server: object
    site: object
    section: Optional[object]
    group: Optional[object]
    allow_private: bool
    prefix: str


def scope_for(token) -> Scope:
    """Build a :class:`Scope` from an ``MCPToken`` and the server it belongs to."""
    server = token.server
    prefix = ""
    if server.group_id is not None:
        prefix = (server.group.path or "").strip("/")
    elif server.section_id is not None:
        prefix = (server.section.path or "").strip("/")
    return Scope(
        server=server,
        site=server.site,
        section=server.section,
        group=server.group,
        allow_private=bool(token.allow_private),
        prefix=prefix,
    )


def in_scope(path: str, prefix: str) -> bool:
    """Return True when ``path`` lives inside the scope's folder prefix."""
    prefix = (prefix or "").strip("/")
    if not prefix:
        return True
    path = (path or "").strip("/")
    return path == prefix or path.startswith(prefix + "/")


def filter_tree(nodes: list[NavigationNode], prefix: str) -> list[NavigationNode]:
    """Return a NEW tree containing only in-scope documents.

    Folder nodes that end up with no children are dropped. Input nodes are
    never mutated.
    """
    out: list[NavigationNode] = []
    for node in nodes:
        if node.type == "document":
            if in_scope(node.path, prefix):
                out.append(node)
            continue
        children = filter_tree(node.children, prefix)
        if children:
            out.append(dataclasses.replace(node, children=children))
    return out


def _node_summary(node) -> Optional[dict]:
    if node is None:
        return None
    return {
        "id": node.pk,
        "title": node.title,
        "path": node.path,
        "type": node.type,
    }


class ScopedDocumentation:
    """Read-only documentation access restricted to a token's scope."""

    def __init__(self, scope: Scope):
        self.scope = scope
        self.service = DocumentationService(
            scope.site,
            authenticated=scope.allow_private,
        )

    def paths(self) -> list[str]:
        return [
            node.path
            for node in flatten(self.service.tree())
            if in_scope(node.path, self.scope.prefix)
        ]

    def allowed_paths(self) -> set[str]:
        return set(self.paths())

    def tree(self) -> list[NavigationNode]:
        return filter_tree(self.service.tree(), self.scope.prefix)

    def search(self, query: str, limit: int = 20) -> list[dict]:
        results = query_documents(
            self.scope.site.source,
            query,
            allowed_paths=self.allowed_paths(),
        )
        return results[:limit]

    def document(self, path: str):
        path = (path or "").strip("/")
        if path not in self.allowed_paths():
            return None
        return self.service.document(path)

    def get_scope_dict(self) -> dict:
        return {
            "server": {
                "id": self.scope.server.pk,
                "name": self.scope.server.name,
                "slug": self.scope.server.slug,
            },
            "site": {
                "id": self.scope.site.pk,
                "name": self.scope.site.name,
                "slug": self.scope.site.slug,
            },
            "section": _node_summary(self.scope.section),
            "group": _node_summary(self.scope.group),
            "allow_private": self.scope.allow_private,
            "prefix": self.scope.prefix,
        }
