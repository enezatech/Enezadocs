from __future__ import annotations

from django.conf import settings

DEFAULTS = {
    "ENABLED": True,
    "LEXICAL_BACKEND": "fts5",
    "EMBEDDINGS_BACKEND": "fastembed",
    "EMBEDDINGS_MODEL": "BAAI/bge-small-en-v1.5",
    "CHUNK_CHARS": 1000,
    "CHUNK_OVERLAP": 200,
    "RRF_K": 60,
    "TOP_K": 20,
}


def search_config() -> dict:
    """Return the merged semantic-search configuration."""
    config = dict(DEFAULTS)
    config.update(getattr(settings, "DOCS_SEMANTIC_SEARCH", {}) or {})
    return config


def embeddings_config() -> dict:
    """Return the embedder subset of the semantic-search configuration."""
    config = search_config()
    return {
        "enabled": bool(config.get("ENABLED")),
        "backend": config.get("EMBEDDINGS_BACKEND") or "fastembed",
        "model": config.get("EMBEDDINGS_MODEL") or "BAAI/bge-small-en-v1.5",
    }
