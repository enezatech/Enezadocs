---
menu name: MCP Content Pagination
position: 3
---

# Planure: MCP Content Pagination (fix truncation on large pages)

> Status: **Implemented**. The authoritative planure lives at
> `feature_Planure/feature_Planure_mcp_content_pagination.md`; this page mirrors it for the
> documentation site.

## Problem

`get_document` returned raw markdown **and** rendered HTML in a single response. Large guides
produced several-hundred-kilobyte tool results that MCP hosts truncated, so agents could not
read them in one call.

## Change

- `get_document(path, format="markdown", offset=0, max_chars=0)` — one representation
  (`markdown` default, `html` opt-in), paginated with `truncated` / `next_offset`.
- `get_document_meta(path)` — metadata, headings, neighbours, and sizes without the body.
- `get_document_section(path, heading, ...)` — one markdown section by heading id or text.
- `MCP_MAX_CONTENT_CHARS` setting (default `40000`) bounds characters per call.
- The `docs://<path>` resource is unchanged (already markdown-only).

## Files

- `apps/documentation/mcp_server/server.py`
- `config/settings.py`
- `docs/Developer/mcp-documentation-server.md`

## Validation (user-run — agent does not test)

1. `manage.py run_mcp`.
2. `get_document_meta` on a large guide → metadata only, no body.
3. `get_document` with no arguments → markdown only, no `html`, `truncated=false` under the cap.
4. Oversized page → follow `next_offset` until `truncated=false`; slices reconstruct the body.
5. `get_document_section` by heading id and by text → only that section.
6. `format="html"` returns HTML; an unknown format raises.

## Notes

- Breaking tool-shape change: `html` is no longer in the default `get_document` response.
- Section slugs are best-effort; heading-text matching is the fallback.
