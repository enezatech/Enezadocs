# Planure: Hybrid Semantic Search (FTS5/BM25 + local embeddings)

> Status: **Implemented** (user selected the hybrid approach; recorded here for traceability).

## Feature Overview

**Problem.** `search_docs` matched the entire query string as a literal substring of one
`content` blob per document (`services/search.py:53`). Natural-language queries such as
"how is the url added" returned nothing because that exact phrase never appears; only
single keywords matched. There was no synonym or paraphrase matching.

**Objective.** Replace substring matching with hybrid retrieval:
1. **Lexical** — tokenized BM25 ranking (SQLite FTS5, with a pure-Python BM25 fallback).
2. **Semantic** — local embedding similarity over heading-aware document chunks.
3. **Fusion** — Reciprocal Rank Fusion of the two ranked lists, aggregated to document level so
   the existing `search_docs` response shape is unchanged.

**Success criteria (user-verified).**
- A multi-word query such as "how is the url added" returns the Eneza CLI Developer Guide.
- Ranking is tokenized, not whole-phrase.
- With `fastembed` installed and the index rebuilt, paraphrase/synonym queries match semantically.
- Without the embedder installed, search degrades to lexical-only with no errors.
- No documentation text leaves the machine (local embeddings only).

## Components & Modules Involved

**New files**
- `apps/documentation/services/semantic.py` — merged search configuration.
- `apps/documentation/services/chunking.py` — heading-aware markdown chunker.
- `apps/documentation/services/embeddings.py` — embedder backends, vector encode/decode, cosine.
- `apps/documentation/migrations/0010_documentationchunk.py` — `DocumentationChunk` table.

**Files changed**
- `apps/documentation/models.py` — add `DocumentationChunk`.
- `apps/documentation/services/search.py` — hybrid index build + query; add `tokenize`.
- `config/settings.py` — add `DOCS_SEMANTIC_SEARCH`.
- `requirements.txt` — add `fastembed`.
- `docs/Developer/mcp-documentation-server.md` — search section.

**Reused (unchanged)**
- `build_docs_index` management command (still calls `build_index(service)`).
- `DocumentationSearchDocument` (now one row per document, as before).
- `parse_frontmatter` / `plain_text` (still exported; used by `validate_docs`).

## High-Level Implementation Steps

1. **Settings.** Add `DOCS_SEMANTIC_SEARCH` (enabled, lexical backend, embedder backend/model,
   chunk size, RRF constant, top-k). *Done.*
2. **Chunking.** `chunk_markdown(body)` produces heading-aware, size-bounded pieces. *Done.*
3. **Embeddings.** `get_embedder()` returns a `fastembed` backend or a no-op embedder when
   unavailable; `encode_vector`/`decode_vector`/`cosine_similarity` helpers. *Done.*
4. **Model + migration.** `DocumentationChunk` (source, path, ordinal, heading, content,
   embedding, token_count) with a unique `(source, path, ordinal)` constraint. *Done.*
5. **Index build.** `build_index` now writes documents, chunks, FTS rows, then embeddings. *Done.*
6. **Hybrid query.** `query_documents` computes lexical (FTS5 → BM25 fallback) and semantic
   scores, fuses them with RRF, and returns document-level results. *Done.*
7. **Dependencies + docs.** Add `fastembed`; document the search section. *Done.*

## Validation (user-run — agent does not test)

1. `pip install -r requirements.txt` (installs `fastembed` + ONNX runtime; the model downloads
   on first use).
2. `python manage.py migrate` (applies `0010_documentationchunk`).
3. `python manage.py build_docs_index` — confirm chunks are created and embeddings are written
   (`DocumentationChunk.objects.filter(embedding__isnull=False).count()` > 0).
4. `search_docs("how is the url added")` — expect the Eneza CLI Developer Guide to rank first.
5. Try a paraphrase that shares no keywords with the text — expect a relevant document to rank.
6. Uninstall/disable `fastembed` and repeat step 4 — expect lexical-only results, no errors.
7. Confirm `search_docs` returns the same shape (`score`, `title`, `path`, `description`) and
   that scope filtering still excludes out-of-scope paths.

## Risks / Notes

- **FTS5 availability.** FTS5 must be compiled into the SQLite build. The code probes for it and
  falls back to pure-Python BM25 automatically.
- **Index rebuild required.** Embeddings are written at index time; run `build_docs_index` after
  doc changes. Hook it into `sync_docs` if you want it automatic.
- **First-query latency.** The local model loads on first use; subsequent queries are fast.
- **Brute-force cosine.** SQLite has no vector index; similarity is computed in Python. Fine for
  hundreds to low-thousands of chunks; move to `sqlite-vec`/pgvector if the corpus grows.
- **Raw FTS table.** `documentation_search_fts` is a sidecar virtual table created lazily, not a
  Django model. It is rebuilt per source during indexing.
- **Model field convention** (repo rule) applied to `DocumentationChunk`.

## Out of Scope

- API/remote embedding providers (local only, for privacy).
- Chunk-level results in the MCP response shape (kept document-level).
- Vector index extensions (`sqlite-vec`, pgvector).
- Automatic reindex on a schedule or file watcher.
- Agent-run testing.
