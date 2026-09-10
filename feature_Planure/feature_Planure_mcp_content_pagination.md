# Planure: MCP Content Pagination (fix truncation on large pages)

> Status: **Implemented** (user approved the fix and it is recorded here for traceability).

## Feature Overview

**Problem.** The MCP `get_document` tool returned the raw markdown **and** the fully
rendered HTML in one response (see `_document_dict` in
`apps/documentation/mcp_server/server.py`). For large guides the payload reached several
hundred kilobytes, so MCP hosts truncated the tool result before the agent could use it —
long documents could only be read by paging the host's dumped output file.

**Objective.** Make every MCP read call small and resumable so no single response is
truncated, while preserving full access to long pages.

**Success criteria (user-verified).**
- `get_document` returns markdown only by default; HTML is opt-in via `format="html"`.
- Long pages are paginated with an explicit `truncated` flag and `next_offset` cursor that
  the agent can pass back as `offset`.
- A metadata-only tool and a section-read tool let an agent fetch only what it needs.
- The response size per call is bounded by the `MCP_MAX_CONTENT_CHARS` setting.

## Components & Modules Involved

**Files changed**
- `apps/documentation/mcp_server/server.py` — reworked `get_document`, added
  `get_document_meta` and `get_document_section`, added pagination/outline helpers.
- `config/settings.py` — added `MCP_MAX_CONTENT_CHARS` (default `40000`).
- `docs/Developer/mcp-documentation-server.md` — documented the new tool surface and
  pagination contract.

**Reused (unchanged)**
- `docs://<path>` resource — already returned markdown only and remains the full-content
  escape hatch.
- `documentation.services.markdown.slugify` — heading id slugs.
- `documentation.services.search.parse_frontmatter` — strips frontmatter before outlining.

## High-Level Implementation Steps

1. **Add the content cap setting.** `MCP_MAX_CONTENT_CHARS` (env-driven, default `40000`)
   defines the default characters returned per call. *Done.*
2. **Stop returning HTML by default.** `get_document(path, format="markdown", offset=0,
   max_chars=0)` returns one representation (`markdown` or `html`) under `content`. *Done.*
3. **Add resumable pagination.** Responses include `content_offset`, `content_returned`,
   `content_total`, `truncated`, and `next_offset`; callers continue with `offset`. *Done.*
4. **Add `get_document_meta(path)`.** Returns metadata, headings, neighbours, and body sizes
   without the body, so an agent can plan before fetching. *Done.*
5. **Add `get_document_section(path, heading, ...)`.** Reads one markdown section selected by
   heading id or text (case-insensitive, partial match allowed). *Done.*
6. **Document the surface.** Update the MCP developer note (tools table, "Reading large
   pages", settings table). *Done.*

## Validation (user-run — agent does not test)

1. Restart the MCP endpoint (`python manage.py run_mcp`).
2. Call `get_document_meta` for a large guide — no body, `content_length` reported.
3. Call `get_document` with no arguments — markdown only, no `html` field, and
   `truncated=false` for pages under the cap.
4. For a page over the cap, follow `next_offset` until `truncated=false`; confirm the
   concatenated slices equal the full markdown.
5. Call `get_document_section` with a heading id from `headings` and with its plain text;
   confirm the returned slice spans that section only.
6. Confirm `format="html"` returns HTML and an unknown format raises an error.

## Risks / Notes

- **Breaking change for the tool shape.** `get_document` no longer returns an `html` field by
  default; clients that relied on it must pass `format="html"`. The `docs://<path>` resource
  is unchanged.
- **Section ids are best-effort.** Section matching uses slugs derived from the markdown
  headings, which may differ from the renderer's HTML anchor ids when a heading repeats.
  Matching by text is the reliable fallback.
- **Model field convention** (repo rule) applies to any future model edits; none were needed
  here.

## Out of Scope

- Changing the `docs://<path>` resource payload or host-side output caps.
- Streaming/chunked transport; pagination is caller-driven.
- Reconciling server content with the local `docs/` tree.
- Agent-run testing.
