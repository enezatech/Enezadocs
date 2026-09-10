from __future__ import annotations

import array
import math

from .semantic import embeddings_config


class BaseEmbedder:
    name = "none"
    model_name = ""

    @property
    def available(self) -> bool:
        return False

    def embed(self, texts):
        return []


class NullEmbedder(BaseEmbedder):
    pass


class FastEmbedEmbedder(BaseEmbedder):
    name = "fastembed"

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        try:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=model_name)
        except Exception:
            self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def embed(self, texts):
        if self._model is None:
            return []
        return [
            [float(value) for value in vector]
            for vector in self._model.embed(list(texts))
        ]


_CACHE: dict = {}


def get_embedder(config: dict | None = None) -> BaseEmbedder:
    """Return the configured embedder, or a no-op embedder when unavailable."""
    config = config or embeddings_config()
    if not config.get("enabled"):
        return NullEmbedder()
    backend = (config.get("backend") or "fastembed").lower()
    model = config.get("model") or "BAAI/bge-small-en-v1.5"
    key = (backend, model)
    if key not in _CACHE:
        if backend == "fastembed":
            _CACHE[key] = FastEmbedEmbedder(model)
        else:
            _CACHE[key] = NullEmbedder()
    return _CACHE[key]


def encode_vector(vector) -> bytes | None:
    if not vector:
        return None
    return array.array("f", vector).tobytes()


def decode_vector(blob) -> list[float]:
    if not blob:
        return []
    values = array.array("f")
    values.frombytes(bytes(blob))
    return values.tolist()


def cosine_similarity(left, right) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (math.sqrt(left_norm) * math.sqrt(right_norm))
