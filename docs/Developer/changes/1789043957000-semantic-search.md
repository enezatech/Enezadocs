# Planure: Hybrid Semantic Search (FTS5/BM25 + local embeddings)

> Status: **Implemented**. The authoritative planure lives at
> `feature_Planure/feature_Planure_semantic_search.md`; this page mirrors it for the
> documentation site.

## Problem

`search_docs` matched the whole query as a literal substring, so natural-language questions
like "how is the url added" returned nothing. No synonym or paraphrase matching existed.

## Change

Hybrid retrieval, document-level results (response shape unchanged):

- **Lexical** — tokenized BM25 via SQLite FTS5, with a pure-Python BM25 fallback when FTS5 is
  unavailable.
- **Semantic** — local `fastembed` embeddings over heading-aware chunks, compared by cosine
  similarity.
- **Fusion** — Reciprocal Rank Fusion of both ranked lists.

## Files

- `apps/documentation/services/semantic.py` (new)
- `apps/documentation/services/chunking.py` (new)
- `apps/documentation/services/embeddings.py` (new)
- `apps/documentation/migrations/0010_documentationchunk.py` (new)
- `apps/documentation/models.py` — `DocumentationChunk`
- `apps/documentation/services/search.py` — hybrid index build and query
- `config/settings.py` — `DOCS_SEMANTIC_SEARCH`
- `requirements.txt` — `fastembed`
- `docs/Developer/mcp-documentation-server.md` — Search section

## Validation (user-run — agent does not test)

1. `pip install -r requirements.txt`
2. `python manage.py migrate`
3. `python manage.py build_docs_index`
4. `search_docs("how is the url added")` → Eneza CLI Developer Guide first.
5. Paraphrase query with no shared keywords → relevant document ranks.
6. Disable `fastembed` → lexical-only results, no errors.

## Notes

- Embeddings are local; no content is sent to a third party.
- Run `build_docs_index` after documentation changes.
- Similarity is brute-force cosine; fine for small corpora.
