from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ProviderUnavailable(Exception):
    pass


class NotFound(Exception):
    pass


@dataclass
class NavigationNode:
    title: str
    path: str = ""
    type: str = "document"
    order: int | None = None
    open: bool = False
    uid: str = ""
    key: str = ""
    children: list["NavigationNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "path": self.path,
            "type": self.type,
            "order": self.order,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class DocumentationDocument:
    title: str
    path: str
    content: str = ""
    html: str = ""
    description: str = ""
    headings: list = field(default_factory=list)
    breadcrumbs: list = field(default_factory=list)
    previous: dict | None = None
    next: dict | None = None
    source_url: str | None = None
    edit_url: str | None = None
    hidden: bool = False
    draft: bool = False


class DocumentationProvider(Protocol):
    def get_tree(self) -> list[NavigationNode]:
        ...

    def get_document(self, path: str) -> str | None:
        ...

    def exists(self, path: str) -> bool:
        ...

    def get_asset(self, path: str) -> tuple[bytes, str] | None:
        ...

    def get_source_url(self, path: str) -> str | None:
        ...

    def get_edit_url(self, path: str) -> str | None:
        ...

    def save_document(self, path: str, content: bytes) -> None:
        """Persist markdown at the provider-relative ``path`` (without ``.md``)."""
        ...
