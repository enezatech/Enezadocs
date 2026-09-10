from __future__ import annotations

import math
import re

import frontmatter
from django.db import DatabaseError, connection

from documentation.models import DocumentationChunk, DocumentationSearchDocument

from .chunking import chunk_markdown
from .embeddings import cosine_similarity, decode_vector, encode_vector, get_embedder
from .navigation import flatten, title_from_name
from .semantic import embeddings_config, search_config

TOKEN_RE = re.compile(r"[a-z0-9]+")
FTS_TABLE = "documentation_search_fts"

_fts_state = None


def parse_frontmatter(raw):
    try:
        post = frontmatter.loads(raw)
        return dict(post.metadata or {}), post.content or ""
    except Exception:
        return {}, raw or ""


def plain_text(raw):
    text = re.sub(r"^---\n[\s\S]*?\n---\n?", "", raw or "")
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
    text = re.sub(r"^>\s?", "", text, flags=re.M)
    text = re.sub(r"[*_>#\[\]|]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text):
    return TOKEN_RE.findall((text or "").lower())


def build_index(service):
    """Rebuild the search index: documents, chunks, vectors, and the FTS table."""
    source = service.source
    config = search_config()
    embedder = get_embedder(embeddings_config())

    DocumentationSearchDocument.objects.filter(source=source).delete()
    DocumentationChunk.objects.filter(source=source).delete()

    fts_rows = []
    for node in flatten(service.tree()):
        raw = service.get_raw(node.path)
        if raw is None:
            continue
        metadata, body = parse_frontmatter(raw)
        title = str(metadata.get("title") or "").strip() or title_from_name(node.path)
        description = str(metadata.get("description") or "").strip()
        text = plain_text(body)
        DocumentationSearchDocument.objects.create(
            source=source,
            path=node.path,
            title=title,
            description=description,
            content=text,
        )
        fts_rows.append((source.pk, node.path, text))
        chunks = [
            DocumentationChunk(
                source=source,
                path=node.path,
                ordinal=chunk["ordinal"],
                heading=chunk["heading"],
                content=chunk["content"],
                token_count=len(tokenize(chunk["content"])),
            )
            for chunk in chunk_markdown(
                body,
                config["CHUNK_CHARS"],
                config["CHUNK_OVERLAP"],
            )
        ]
        if chunks:
            DocumentationChunk.objects.bulk_create(chunks, batch_size=200)

    _refresh_fts(source, fts_rows)
    _embed_source(source, embedder)


def query_documents(source, query, allowed_paths=None):
    """Hybrid search: lexical (FTS5/BM25) fused with embedding similarity."""
    query = (query or "").strip()
    if not query:
        return []

    config = search_config()
    documents = list(DocumentationSearchDocument.objects.filter(source=source))
    if allowed_paths is not None:
        documents = [doc for doc in documents if doc.path in allowed_paths]
    if not documents:
        return []

    by_path = {doc.path: doc for doc in documents}
    tokens = tokenize(query)

    lexical = _lexical_scores(source, tokens, documents, config)
    semantic = _semantic_scores(source, query, set(by_path))
    fused = _fuse(lexical, semantic, config["RRF_K"])

    results = []
    for path, score in sorted(fused.items(), key=lambda item: -item[1]):
        document = by_path.get(path)
        if document is None:
            continue
        results.append(
            {
                "score": round(score, 6),
                "title": document.title,
                "path": document.path,
                "description": document.description,
            },
        )
        if len(results) >= config["TOP_K"]:
            break
    return results


def _lexical_scores(source, tokens, documents, config):
    if not tokens:
        return {}
    backend = (config.get("LEXICAL_BACKEND") or "bm25").lower()
    if backend == "fts5":
        allowed = {doc.path for doc in documents}
        scores = _fts_scores(source, tokens)
        scores = {path: score for path, score in scores.items() if path in allowed}
        if scores:
            return scores
    return _bm25_scores(
        [(doc.path, tokenize(doc.content)) for doc in documents],
        tokens,
    )


def _bm25_scores(documents, query_tokens, k1=1.5, b=0.75):
    count = len(documents)
    if not count or not query_tokens:
        return {}
    lengths = [len(tokens) for _, tokens in documents]
    average = sum(lengths) / count or 1.0
    query_terms = set(query_tokens)
    doc_freq = {term: 0 for term in query_terms}
    for _, tokens in documents:
        present = set(tokens) & query_terms
        for term in present:
            doc_freq[term] += 1

    scores = {}
    for path, tokens in documents:
        length = len(tokens) or 1
        frequencies = {}
        for token in tokens:
            if token in query_terms:
                frequencies[token] = frequencies.get(token, 0) + 1
        score = 0.0
        for term, frequency in frequencies.items():
            df = doc_freq[term]
            idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1 - b + b * length / average)
            score += idf * (frequency * (k1 + 1)) / denominator
        if score > 0:
            scores[path] = score
    return scores


def _fts_supported():
    global _fts_state
    if _fts_state is not None:
        return _fts_state
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} "
                "USING fts5(source_id UNINDEXED, path UNINDEXED, content)",
            )
        _fts_state = True
    except DatabaseError:
        _fts_state = False
    return _fts_state


def _refresh_fts(source, rows):
    if not _fts_supported():
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {FTS_TABLE} WHERE source_id = %s",
                [source.pk],
            )
            if rows:
                cursor.executemany(
                    f"INSERT INTO {FTS_TABLE} (source_id, path, content) "
                    "VALUES (%s, %s, %s)",
                    rows,
                )
    except DatabaseError:
        return


def _fts_scores(source, tokens):
    if not tokens or not _fts_supported():
        return {}
    match = " OR ".join(f'"{token}"' for token in tokens)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT path, bm25({FTS_TABLE}) FROM {FTS_TABLE} "
                f"WHERE source_id = %s AND {FTS_TABLE} MATCH %s",
                [source.pk, match],
            )
            rows = cursor.fetchall()
    except DatabaseError:
        return {}
    return {path: -float(rank) for path, rank in rows}


def _semantic_scores(source, query, allowed_paths):
    embedder = get_embedder(embeddings_config())
    if not embedder.available:
        return {}
    vectors = embedder.embed([query])
    if not vectors:
        return {}
    query_vector = vectors[0]
    scores = {}
    try:
        chunks = DocumentationChunk.objects.filter(
            source=source,
            embedding__isnull=False,
        )
        chunks = list(chunks)
    except DatabaseError:
        return {}
    for chunk in chunks:
        if chunk.path not in allowed_paths:
            continue
        similarity = cosine_similarity(query_vector, decode_vector(chunk.embedding))
        if similarity > scores.get(chunk.path, -1.0):
            scores[chunk.path] = similarity
    return scores


def _fuse(lexical, semantic, k):
    fused = {}
    for rank, (path, _) in enumerate(
        sorted(lexical.items(), key=lambda item: -item[1]),
        start=1,
    ):
        fused[path] = fused.get(path, 0.0) + 1.0 / (k + rank)
    for rank, (path, _) in enumerate(
        sorted(semantic.items(), key=lambda item: -item[1]),
        start=1,
    ):
        fused[path] = fused.get(path, 0.0) + 1.0 / (k + rank)
    return fused


def _embed_source(source, embedder, batch_size=32):
    if not embedder.available:
        return
    chunks = list(DocumentationChunk.objects.filter(source=source))
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = embedder.embed([chunk.content for chunk in batch])
        for chunk, vector in zip(batch, vectors):
            chunk.embedding = encode_vector(vector)
        DocumentationChunk.objects.bulk_update(batch, ["embedding"])
