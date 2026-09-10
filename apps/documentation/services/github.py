from __future__ import annotations

import base64
import mimetypes

import requests
from django.conf import settings

from .base import NavigationNode, NotFound, ProviderUnavailable
from .navigation import build_tree_from_paths


class GitHubClient:
    base = "https://api.github.com"

    def __init__(self, config):
        self.config = config

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "enezadocs",
        }
        token = self._resolve_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _resolve_token(self) -> str:
        credential = getattr(self.config, "credential", None)
        if credential is not None:
            try:
                token = credential.token
            except Exception:
                token = ""
            if token:
                return token
        return getattr(settings, "GITHUB_TOKEN", "") or ""

    def _get(self, url: str) -> requests.Response:
        try:
            resp = requests.get(url, headers=self._headers(), timeout=15)
        except requests.RequestException as exc:
            raise ProviderUnavailable(str(exc)) from exc
        if resp.status_code == 404:
            raise NotFound(f"GitHub API 404: {url}")
        if resp.status_code >= 400:
            raise ProviderUnavailable(f"GitHub API {resp.status_code}")
        return resp

    def get_tree(self) -> list[str]:
        cfg = self.config
        url = (
            f"{self.base}/repos/{cfg.owner}/{cfg.repository}/"
            f"git/trees/{cfg.branch}?recursive=1"
        )
        data = self._get(url).json()
        return [
            entry.get("path", "")
            for entry in data.get("tree", [])
            if entry.get("type") == "blob"
        ]

    def get_latest_commit_sha(self) -> str:
        cfg = self.config
        url = f"{self.base}/repos/{cfg.owner}/{cfg.repository}/commits/{cfg.branch}"
        data = self._get(url).json()
        return data.get("sha", "") or ""

    def get_raw(self, path: str) -> bytes:
        cfg = self.config
        url = (
            f"{self.base}/repos/{cfg.owner}/{cfg.repository}/"
            f"contents/{path}?ref={cfg.branch}"
        )
        data = self._get(url).json()
        if data.get("encoding") == "base64" and data.get("content"):
            return base64.b64decode(data["content"])
        return b""

    def get_raw_text(self, path: str) -> str:
        return self.get_raw(path).decode("utf-8", errors="replace")


class GitHubDocumentationProvider:
    def __init__(self, config):
        self.config = config
        self.client = GitHubClient(config)

    def _full_path(self, rel: str) -> str:
        prefix = self.config.root_path.strip("/")
        rel = rel.strip("/")
        return f"{prefix}/{rel}" if prefix else rel

    def get_tree(self) -> list[NavigationNode]:
        prefix = self.config.root_path.strip("/")
        paths: list[str] = []
        for full in self.client.get_tree():
            if not full.endswith(".md"):
                continue
            if prefix and not full.startswith(f"{prefix}/"):
                continue
            rel = full[len(prefix) :].strip("/") if prefix else full
            if rel.endswith(".md"):
                rel = rel[:-3]
            paths.append(rel)
        return build_tree_from_paths(paths)

    def get_document(self, path: str) -> str | None:
        full = self._full_path(f"{path}.md")
        try:
            return self.client.get_raw_text(full)
        except NotFound:
            return None

    def exists(self, path: str) -> bool:
        try:
            self.client.get_raw(self._full_path(f"{path}.md"))
            return True
        except (NotFound, ProviderUnavailable):
            return False

    def get_asset(self, path: str) -> tuple[bytes, str] | None:
        try:
            data = self.client.get_raw(self._full_path(path))
        except (NotFound, ProviderUnavailable):
            return None
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        return data, content_type

    def get_source_url(self, path: str) -> str | None:
        cfg = self.config
        full = self._full_path(f"{path}.md")
        return f"https://github.com/{cfg.owner}/{cfg.repository}/blob/{cfg.branch}/{full}"

    def get_edit_url(self, path: str) -> str | None:
        cfg = self.config
        full = self._full_path(f"{path}.md")
        return f"https://github.com/{cfg.owner}/{cfg.repository}/edit/{cfg.branch}/{full}"
