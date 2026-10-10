---
menu name: Docs & Home Performance Caching
position: 13
---

# Change: Faster documentation and home-page loads

**Date:** 2026-10-10

## Goal

Make opening a document at most one GitHub *tree* call (usually zero) instead of
one content call per page, make the home page reuse cheap shared data instead of
rebuilding a tree per featured site on every request, share caches across all
processes, and stop re-rendering unchanged documents.

Root causes addressed: every doc view rebuilt the full navigation tree by reading
**every page body** over the network; tree/document caches were per-process
`LocMemCache` so invalidation never reached sibling uvicorn workers; rendered
HTML was never cached; and the home page rebuilt featured-site trees and loaded
`HomePage` on every request.

## What changed

| Area | Change |
| --- | --- |
| Model + migration | `DocumentationSearchDocument` gains `nav_label`, `nav_order`, `access` (migration `0013_documentationsearchdocument_nav_metadata.py`). |
| Shared metadata helper | `services/access.py` adds `label_and_order(metadata, fallback)`, the menu-name/position parsing previously private to `structure.py`; `structure.py` and `search.py` reuse it. |
| Persist nav metadata | `services/search.py` `build_index` writes `nav_label`/`nav_order`/`access` on each `DocumentationSearchDocument` from the frontmatter it already parses (no extra fetch). |
| Tree without body reads | `services/structure.py` `build_structure_tree` accepts a `page_meta` map `{path: (label, order, access)}`; a path present in the map is labelled and privacy-filtered without reading the body, while a **missing** path keeps the `read_raw` fallback so unindexed/stale sources stay correct. |
| Metadata map | `services/documentation.py` adds `page_meta_map()`, read once via `values_list` (avoids the large `content` column) and cached per source under `docs:source:{id}:pagemeta` when non-empty. `_tree` passes it only when caching is on. |
| Rendered-doc cache | `document()` caches the renderer's dict (`title`, `description`, `hidden`, `draft`, `html`, `headings`) under `docs:site:{id}:render:{path}` with `DOCS_CACHE_RENDER_TTL`; breadcrumbs/prev/next/source URLs stay per-request. |
| Cache backend | `config/settings.py` selects `DOCS_CACHE_BACKEND` (`db` → `DatabaseCache` on `DOCS_CACHE_TABLE` with `MAX_ENTRIES=10000`; otherwise the existing `LocMemCache`). Adds `DOCS_CACHE_RENDER_TTL` and `DOCS_CACHE_HOME_TTL`. |
| Invalidation | `rebuild_index_for_source()` and the `build_docs_index` command now call `invalidate_source()` after indexing, so the metadata map cached during indexing is dropped. The DB cache has no `delete_pattern`, so `invalidate_source` falls back to `cache.clear()`, which reaches every process. |
| Home caching | `views.py` `HomeView` caches the context per auth scope (`docs:home:ctx:public` / `:full`) and fixes N+1s with `select_related("source")`, `featured_sites.select_related("site")`, and `updates.select_related("site")`. |
| Branding cache | `context_processors.site_branding` caches `HomePage.load()` under `docs:home:page` (`DOCS_CACHE_HOME_TTL`), removing a `get_or_create` query per request site-wide. |
| Home invalidation | New `clear_home_cache()` in `services/documentation.py` deletes `docs:home:page` and both context keys; called from `HomePageAdmin` and `DocumentationSiteAdmin` save/delete hooks. |
| Deployment | `docker/entrypoint.sh` and `docker/worker.sh` run `python manage.py createcachetable`; `docker-compose.yml` sets `DOCS_CACHE_BACKEND=db` for `web` and `worker`; `.env.sample` documents the new cache settings. |

## Notes

- The cache defaults to `locmem`; Docker/Coolify set `db` so all workers share one cache. After deploying to an existing instance, run `python manage.py build_docs_index` once (or **Sync documentation**) so rows carry navigation metadata; until then the tree falls back to reading each page body.
- Privacy safety: a page absent from the metadata map is still read raw and honors `access`, so anonymous visitors cannot see private pages.
- Home context is cached per auth scope (featured content differs for anonymous vs. authenticated); both keys are cleared together.
- Invalidation is blunt (`cache.clear()` on each sync) because `DatabaseCache` has no `delete_pattern`; acceptable for a rare background job.
- Cache keys are coarse (one tree key per scope, one metadata key per source, one render key per document, two home keys) to bound extra SQL round-trips.
- No new Python dependency (Django's built-in database cache).
- Agent does not test; the user is solely responsible for testing and validation.

## User validation

1. `python manage.py migrate` (applies `0013`) and `python manage.py createcachetable` (creates `docs_cache_table`).
2. `python manage.py build_docs_index` — confirm rows carry `nav_label`/`nav_order`/`access` (e.g. `DocumentationSearchDocument.objects.exclude(nav_label="").count() > 0`).
3. Open a GitHub-backed doc URL twice; on the second (warm) open, confirm no GitHub `/contents/...` requests occur and the page renders.
4. Load the home page twice; confirm the second load serves from cache with no per-page GitHub content requests, and featured docs list the expected pages for both anonymous and logged-in visitors.
5. Confirm sidebar labels/ordering, prev/next, breadcrumbs, and a private page hidden from an anonymous visitor behave as before.
6. Trigger **Sync documentation** and confirm all workers reflect updated content (no stale cache); edit the `HomePage` in admin and confirm the home page updates.
7. Verify search and MCP (`get_navigation`, `get_document`) return the same shapes.
