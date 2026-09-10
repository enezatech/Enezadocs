from __future__ import annotations

import mimetypes
from functools import cached_property

from django.conf import settings

from .base import NavigationNode, ProviderUnavailable
from .navigation import build_tree_from_paths

MISSING_CODES = {"NoSuchKey", "NoSuchBucket", "404", "NotFound"}


def s3_settings() -> dict:
    return getattr(settings, "DOCS_S3", {}) or {}


def s3_enabled() -> bool:
    """True when a documentation bucket is configured in the environment."""
    return bool(s3_settings().get("ENABLED"))


class S3DocumentationProvider:
    """Read-only documentation provider backed by an S3 (or S3-compatible) bucket.

    Selected automatically for LOCAL sources when ``DOCS_S3_BUCKET`` is set;
    otherwise ``LocalDocumentationProvider`` is used. Markdown files are read
    from ``DOCS_S3_PREFIX`` and mirror the filesystem layout (``<path>.md``).
    """

    def __init__(self, config=None):
        self.config = config
        self.settings = s3_settings()

    @cached_property
    def bucket(self) -> str:
        return (self.settings.get("BUCKET") or "").strip()

    @cached_property
    def prefix(self) -> str:
        return (self.settings.get("PREFIX") or "").strip("/")

    @cached_property
    def client(self):
        try:
            import boto3
        except ImportError as exc:
            raise ProviderUnavailable(
                "boto3 is not installed; install it to use S3 storage.",
            ) from exc

        kwargs = {}
        region = self.settings.get("REGION")
        if region:
            kwargs["region_name"] = region
        endpoint = self.settings.get("ENDPOINT_URL")
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        access_key = self.settings.get("ACCESS_KEY_ID")
        secret = self.settings.get("SECRET_ACCESS_KEY")
        if access_key and secret:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret
        if self.settings.get("USE_PATH_STYLE"):
            from botocore.config import Config

            kwargs["config"] = Config(s3={"addressing_style": "path"})
        try:
            return boto3.client("s3", **kwargs)
        except Exception as exc:
            raise ProviderUnavailable(str(exc)) from exc

    def _key(self, rel_path: str) -> str:
        rel = (rel_path or "").strip("/")
        return f"{self.prefix}/{rel}" if self.prefix else rel

    @staticmethod
    def _is_missing(exc: Exception) -> bool:
        response = getattr(exc, "response", None) or {}
        code = response.get("Error", {}).get("Code", "")
        return code in MISSING_CODES

    def _list_keys(self) -> list[str]:
        prefix = f"{self.prefix}/" if self.prefix else ""
        keys: list[str] = []
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj.get("Key", "")
                    if key.endswith(".md"):
                        keys.append(key)
        except Exception as exc:
            if self._is_missing(exc):
                return []
            raise ProviderUnavailable(str(exc)) from exc
        return keys

    def get_tree(self) -> list[NavigationNode]:
        prefix = f"{self.prefix}/" if self.prefix else ""
        paths: list[str] = []
        for key in self._list_keys():
            rel = key[len(prefix):].strip("/") if prefix else key
            if rel.endswith(".md"):
                rel = rel[:-3]
            if rel:
                paths.append(rel)
        return build_tree_from_paths(paths)

    def get_document(self, path: str) -> str | None:
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=self._key(f"{path}.md"),
            )
        except Exception as exc:
            if self._is_missing(exc):
                return None
            raise ProviderUnavailable(str(exc)) from exc
        return response["Body"].read().decode("utf-8", errors="replace")

    def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(f"{path}.md"))
            return True
        except Exception as exc:
            if self._is_missing(exc):
                return False
            raise ProviderUnavailable(str(exc)) from exc

    def get_asset(self, path: str) -> tuple[bytes, str] | None:
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=self._key(path),
            )
        except Exception as exc:
            if self._is_missing(exc):
                return None
            raise ProviderUnavailable(str(exc)) from exc
        data = response["Body"].read()
        content_type = (
            response.get("ContentType")
            or mimetypes.guess_type(path)[0]
            or "application/octet-stream"
        )
        return data, content_type

    def get_source_url(self, path: str) -> str | None:
        return None

    def get_edit_url(self, path: str) -> str | None:
        return None
