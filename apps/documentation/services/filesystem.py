from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from .base import NavigationNode
from .navigation import build_tree_from_paths


class LocalDocumentationProvider:
    def __init__(self, config):
        self.config = config
        self.root = Path(config.root_path).expanduser().resolve()

    def _safe_path(self, rel_path: str) -> Path:
        clean = (rel_path or "").strip("/\\")
        candidate = (self.root / clean).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Path escapes documentation root")
        return candidate

    def _collect_md_paths(self) -> list[str]:
        paths: list[str] = []
        if not self.root.is_dir():
            return paths
        for dirpath, _dirnames, filenames in os.walk(self.root):
            for name in sorted(filenames):
                if name.endswith(".md"):
                    full = Path(dirpath) / name
                    rel = full.relative_to(self.root).as_posix()
                    paths.append(rel[:-3])
        return paths

    def get_tree(self) -> list[NavigationNode]:
        return build_tree_from_paths(self._collect_md_paths())

    def get_document(self, path: str) -> str | None:
        try:
            target = self._safe_path(f"{path}.md")
        except ValueError:
            return None
        if not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    def exists(self, path: str) -> bool:
        try:
            target = self._safe_path(f"{path}.md")
        except ValueError:
            return False
        return target.is_file()

    def get_asset(self, path: str) -> tuple[bytes, str] | None:
        try:
            target = self._safe_path(path)
        except ValueError:
            return None
        if not target.is_file():
            return None
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        return target.read_bytes(), content_type

    def get_source_url(self, path: str) -> str | None:
        return None

    def get_edit_url(self, path: str) -> str | None:
        return None
