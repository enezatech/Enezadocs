---
menu name: MCP Documentation Server
position: 20
---

# MCP Documentation Server

The documentation app exposes read-only [Model Context Protocol](https://modelcontextprotocol.io)
(MCP) servers over Streamable HTTP so AI agents can discover and read documentation.

Servers are **database-backed**: each `MCPServer` row defines its own scope (a site, with an
optional section and group) and its own endpoint, so you can publish several specialized
servers (for example one per product area or audience) from the same app.

## Endpoints

Each server is addressed at the base path plus its slug:

```
<MCP_PATH>/<server-slug>/
# default base path:
/mcp/developer/
/mcp/billing/
```

The base path is the only MCP setting; everything else lives in the database:

| Setting | Environment variable | Default | Purpose |
| --- | --- | --- | --- |
| Endpoint on/off | `MCP_ENABLED` | `1` (on) | Set to `0` to disable all MCP endpoints. |
| Base path | `MCP_PATH` | `/mcp` | Prefix for every server endpoint. |
| Content cap | `MCP_MAX_CONTENT_CHARS` | `40000` | Default characters returned by `get_document`/`get_document_section` per call. |

One command serves the Django site and all MCP endpoints together on a single port:

```bash
python manage.py run_mcp              # http://127.0.0.1:8000
python manage.py run_mcp 0.0.0.0:9000 # custom bind
```

This is a thin wrapper around `uvicorn config.asgi:application`, so the equivalent direct
command also works:

```bash
uvicorn config.asgi:application
```

A request to the base path with no server slug (for example `/mcp/`) returns `404` with a
hint to include a server slug.

## Servers and scoping

A `MCPServer` is bound to:

- **Site** (required) — the documentation site it serves.
- **Section** (optional) — a top-level section node.
- **Group** (optional) — a group node inside that section.

Scope rules:

| Section | Group | The server can read |
| --- | --- | --- |
| — | — | The whole site. |
| set | — | That section and everything below it. |
| set | set | Only that group (it must live inside the section). |

Create servers in the Django admin (**MCP servers**). A server has a **name**, a **slug**
(the URL segment), the scope fields above, and an **enabled** toggle. Disabling a server
takes all of its endpoints offline.

## Tokens

Every request must send `Authorization: Bearer <token>`. Each token belongs to exactly one
`MCPServer` and is only accepted at that server's endpoint; the token inherits the server's
scope. The per-token `allow_private` flag lets a server issue both public-only and
private-capable credentials.

Tokens are stored as a SHA-256 hash for authentication plus an encrypted copy of the raw
value so an admin can re-copy it. On the **MCP tokens** change page the bearer token is shown
with a **Copy** button, and two list actions are available: **Reveal bearer token** (shows the
value for the selected tokens) and **Regenerate bearer token** (issues a new value,
invalidating the old one). Tokens created before the encrypted copy existed show "Not stored"
until regenerated.

Create a token in the admin (**MCP tokens**), or with the management command:

```bash
# Issue a token for an existing server
python manage.py create_mcp_token --name "Docs agent" --server developer

# Create the server (if missing) and issue a token in one step
python manage.py create_mcp_token --name "Docs agent" --server developer \
    --site my-site --section "Developer" --allow-private
```

`--server` is the server slug. `--section`/`--group` accept a node id or title and are only
used when the server is created.

## Tools

| Tool | Purpose |
| --- | --- |
| `get_scope` | Report the server and the site/section/group the token can read. |
| `get_navigation` | Return the scoped navigation tree. |
| `search_docs` | Hybrid search (BM25/FTS5 + embeddings) restricted to the scope. |
| `get_document_meta` | Return a page's metadata and outline (headings, neighbours, sizes) without the body. |
| `get_document` | Read a page by path, markdown by default. |
| `get_document_section` | Read a single markdown section of a page by heading id or text. |

Each page is also exposed as a resource (`docs://<path>`); resource reads are validated
against the same scope.

### Reading large pages

`get_document` does **not** return the rendered HTML alongside the markdown. Pass
`format="html"` to request HTML instead; the default `format="markdown"` returns the
markdown body only. Responses are paginated so a single call cannot exceed the host's
output limit:

| Field | Meaning |
| --- | --- |
| `content` | The requested slice of the selected representation. |
| `content_format` | `markdown` or `html`. |
| `content_offset` / `content_returned` / `content_total` | Slice start, size, and full size (characters). |
| `truncated` | `true` when more content remains. |
| `next_offset` | Pass back as `offset` to continue; `null` when finished. |

`max_chars` caps the returned characters: `0` (default) uses the `MCP_MAX_CONTENT_CHARS`
setting (`40000` by default), and a negative value returns the whole body. To read one part
of a long page, call `get_document_meta` for the outline, then `get_document_section` with
the heading `id` or text — for example `get_document_section(path, "installation")`.

## Search

`search_docs` uses hybrid retrieval: BM25 lexical ranking (SQLite FTS5, with a pure-Python
BM25 fallback when FTS5 is unavailable) fused with local embedding similarity via Reciprocal
Rank Fusion. Results are aggregated to document level, so the response shape is unchanged.

Semantic matching requires the index to contain embeddings. Install `fastembed`, then rebuild:

```bash
pip install -r requirements.txt
python manage.py build_docs_index
```

Configure via `DOCS_SEMANTIC_SEARCH` (all overridable by environment variables):

| Key | Default | Purpose |
| --- | --- | --- |
| `ENABLED` | `True` | Master switch for the hybrid path. |
| `LEXICAL_BACKEND` | `fts5` | `fts5` (fallback to BM25) or `bm25`. |
| `EMBEDDINGS_BACKEND` | `fastembed` | Embedding provider. |
| `EMBEDDINGS_MODEL` | `BAAI/bge-small-en-v1.5` | Local model name. |
| `CHUNK_CHARS` / `CHUNK_OVERLAP` | `1000` / `200` | Chunk size for embeddings. |
| `RRF_K` / `TOP_K` | `60` / `20` | Fusion constant and result cap. |

If the embedder is unavailable the search degrades to lexical-only; nothing breaks. Embeddings
are computed on the server and never sent to a third party.

## Notes

- Re-importing the navigation structure from a provider recreates `DocumentationNode` rows.
  A server's `section`/`group` references are set to `NULL` on delete, so re-check a server's
  scope after a structure rebuild.
- The web app, search index, and access rules are unchanged; MCP only adds scoped, read-only
  views.
