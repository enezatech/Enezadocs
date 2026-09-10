from __future__ import annotations

import posixpath

from django.conf import settings
from django.core.cache import cache

from .base import DocumentationDocument, ProviderUnavailable
from .factory import get_provider
from .markdown import MarkdownRenderer
from .navigation import docs_first, flatten, slugify_path, title_from_name


class NullProvider:
    def get_tree(self):
        return []

    def get_document(self, path):
        return None

    def exists(self, path):
        return False

    def get_asset(self, path):
        return None

    def get_source_url(self, path):
        return None

    def get_edit_url(self, path):
        return None


class DocumentationService:
    def __init__(self, site, authenticated=True):
        self.site = site
        self.source = site.source
        self._authenticated = bool(authenticated)
        try:
            self.provider = get_provider(self.source)
        except Exception:
            self.provider = NullProvider()
        self.renderer = MarkdownRenderer(site.slug, url_path=slugify_path)
        self._structure_mode_cache = None
        self._tree_cache: dict[str, list] = {}
        self._raw_cache: dict[str, str | None] = {}
        self._provider_tree_cache = None
        self._url_map_cache: dict[str, str] | None = None

    def _key(self, kind, path=""):
        return f"docs:site:{self.site.id}:{kind}:{path}"

    @property
    def _use_cache(self) -> bool:
        if not settings.DEBUG:
            return True
        # Remote sources are slow to refetch on every view, so cache them even
        # while DEBUG is on. Local markdown stays uncached so edits appear
        # immediately during development.
        from .s3 import s3_enabled

        return self.source.source_type == "GITHUB" or s3_enabled()

    @property
    def structure_mode(self) -> bool:
        if self._structure_mode_cache is None:
            self._structure_mode_cache = (
                self.site.nodes.filter(
                    enabled=True,
                    type__in=["section", "group"],
                ).exists()
            )
        return self._structure_mode_cache

    def tree(self):
        """Navigation tree visible to the current request scope.

        Scoped by the ``authenticated`` flag passed to the constructor:
        anonymous requests only receive public content.
        """
        return self._tree(self._authenticated)

    def full_tree(self):
        """Navigation tree containing every page, including private content."""
        return self._tree(True)
    def _tree(self, authenticated):
        scope = "full" if authenticated else "public"
        if scope in self._tree_cache:
            return self._tree_cache[scope]
        key = self._key("tree", scope)
        if self._use_cache:
            cached = cache.get(key)
            if cached is not None:
                self._tree_cache[scope] = cached
                return cached
        if self.structure_mode:
            from .structure import build_structure_tree

            provider_tree = self._provider_tree()
            tree = build_structure_tree(
                self.site,
                provider_tree,
                self.get_raw,
                authenticated=authenticated,
            )
        else:
            try:
                tree = self.provider.get_tree()
            except ProviderUnavailable:
                self._tree_cache[scope] = []
                return []
            if not authenticated:
                from .access import filter_public_documents

                tree = filter_public_documents(tree, self._is_private_document)
        tree = docs_first(tree)
        if self._use_cache:
            cache.set(key, tree, settings.DOCS_CACHE_TREE_TTL)
        self._tree_cache[scope] = tree
        return tree
    def _is_private_document(self, node) -> bool:
        from .access import PRIVATE, raw_access

        try:
            raw = self.get_raw(node.path)
        except Exception:
            return False
        if raw is None:
            return False
        return raw_access(raw) == PRIVATE

    def _provider_tree(self):
        if self._provider_tree_cache is not None:
            return self._provider_tree_cache
        try:
            self._provider_tree_cache = self.provider.get_tree()
        except Exception:
            self._provider_tree_cache = []
        return self._provider_tree_cache

    def flat_paths(self):
        return [node.path for node in flatten(self.tree())]

    def full_flat_paths(self):
        return [node.path for node in flatten(self.full_tree())]

    def _url_map(self) -> dict[str, str]:
        """Return ``{url_path: real_path}`` for every document in the full tree.

        Real paths are inserted first so an incoming raw path always resolves to
        itself, then slugified paths are added without overriding a real path.
        """
        if self._url_map_cache is not None:
            return self._url_map_cache
        mapping: dict[str, str] = {}
        for path in self.full_flat_paths():
            mapping[path] = path
        for path in list(mapping):
            mapping.setdefault(slugify_path(path), path)
        self._url_map_cache = mapping
        return mapping

    def resolve_url_path(self, url_path: str) -> str:
        """Map a URL path back to the provider's real path when possible."""
        url_path = (url_path or "").strip("/")
        if not url_path:
            return ""
        return self._url_map().get(url_path, url_path)

    def slugify_path(self, path: str) -> str:
        return slugify_path(path)

    def exists(self, path):
        return (path or "").strip("/") in self.flat_paths()

    def get_raw(self, path):
        if path in self._raw_cache:
            return self._raw_cache[path]
        key = self._key("document", path)
        if self._use_cache:
            cached = cache.get(key)
            if cached is not None:
                self._raw_cache[path] = cached
                return cached
        try:
            raw = self.provider.get_document(path)
        except ProviderUnavailable:
            self._raw_cache[path] = None
            return None
        if raw is None:
            self._raw_cache[path] = None
            return None
        if self._use_cache:
            cache.set(key, raw, settings.DOCS_CACHE_DOCUMENT_TTL)
        self._raw_cache[path] = raw
        return raw

    def document(self, path):
        path = (path or "").strip("/")
        raw = self.get_raw(path)
        if raw is None:
            return None

        rendered = self.renderer.render(raw, path)
        flat = flatten(self.tree())
        order = [node.path for node in flat]
        idx = order.index(path) if path in order else -1
        previous = self._adjacent(flat, idx - 1)
        next_doc = self._adjacent(flat, idx + 1)

        fallback_title = title_from_name(posixpath.basename(path)) if path else self.site.name
        return DocumentationDocument(
            title=rendered["title"] or fallback_title,
            path=path,
            content=raw,
            html=rendered["html"],
            description=rendered["description"],
            headings=rendered["headings"],
            breadcrumbs=self._breadcrumbs(path),
            previous=previous,
            next=next_doc,
            source_url=self._safe(lambda: self.provider.get_source_url(path)),
            edit_url=self._safe(lambda: self.provider.get_edit_url(path)),
            hidden=rendered["hidden"],
            draft=rendered["draft"],
        )

    def _adjacent(self, flat, idx):
        if idx < 0 or idx >= len(flat):
            return None
        node = flat[idx]
        return {"title": node.title, "path": node.path}

    def _breadcrumbs(self, path):
        parts = [p for p in path.split("/") if p]
        crumbs = [{"title": self.site.name, "path": ""}]
        acc = []
        for part in parts[:-1]:
            acc.append(part)
            crumbs.append({"title": title_from_name(part), "path": "/".join(acc)})
        if parts:
            crumbs.append({"title": title_from_name(parts[-1]), "path": path})
        return crumbs

    def _safe(self, fn):
        try:
            return fn()
        except Exception:
            return None

    def nav_tree(self):
        return [node.to_dict() for node in self.tree()]

    def search(self, query):
        from .search import query_documents

        allowed_paths = None
        if not self._authenticated:
            allowed_paths = set(self.flat_paths())
        return query_documents(self.source, query, allowed_paths=allowed_paths)

    def get_asset(self, path):
        from .assets import fetch_asset
        return fetch_asset(self.provider, self.source, path)

    def source_home_url(self):
        if self.source.source_type != "GITHUB":
            return None
        try:
            github = self.source.github
        except Exception:
            return None
        prefix = github.root_path.strip("/")
        base = f"https://github.com/{github.owner}/{github.repository}/tree/{github.branch}"
        return f"{base}/{prefix}" if prefix else base
