# Planure: Faster documentation + home page loads (GitHub sources)

> Status: **Proposed** — awaiting user approval before implementation.
> User is solely responsible for all testing and validation of the output.

## Feature Overview

### Document pages

**Problem.** Opening a document URL for a GitHub-backed site is very slow. Traced cause chain:

1. Every document view builds the *full* navigation tree.
   `DocumentationView.get` (`views.py:165-178`) calls `service.resolve_url_path(path)` →
   `_url_map()` → `full_flat_paths()` → `full_tree()` (`services/documentation.py:150-171`),
   then `flat_paths()`/`full_flat_paths()` again for the privacy check (`views.py:189-204`),
   again in `_context` (`views.py:210-233`) and again in `document()` (`documentation.py:208`).
2. Building the tree reads **every page body** to get frontmatter.
   In structure mode, `build_structure_tree` calls `read_raw` for every page inside each
   section/group folder (`services/structure.py:81-110`), and `get_raw`
   (`documentation.py:179-199`) calls `provider.get_document()` →
   `GitHubDocumentationProvider.get_document` → one GitHub `/contents/...` request per page
   (`services/github.py:109-112`).
3. The tree and document caches expire together (300 s, `settings.py:240-241`), so a
   cold cache turns one page view into **`1 + N` sequential GitHub API calls**, and the
   `1 + N` storm repeats roughly every 5 minutes.
4. `LocMemCache` (`settings.py:223-228`) is per process: the 3 uvicorn workers
   (`UVICORN_WORKERS=3`) each pay the full cost, and `invalidate_source`'s `cache.clear()`
   runs in the background worker process, so it never reaches the web workers
   (`services/sync.py:10-18`).
5. Rendered HTML is never cached: `document()` re-runs frontmatter parsing, Markdown
   conversion, Pygments highlighting and `nh3` sanitizing on every request
   (`documentation.py:201-229`, `services/markdown.py:122-147`).

### Home page

**Problem.** The home page (`HomeView.get`, `views.py:31-118`) is slow for the same root cause
plus its own per-request work:

1. **Per-featured-site full tree build.** `_featured` → `_featured_docs`
   (`views.py:96-118`) constructs a `DocumentationService` and calls `service.tree()` for
   **each** featured site, on **every** home request. That is the same
   `1 + N` GitHub content-fetch storm per featured site (steps 1-3 above), so the home page can
   be several times worse than a single doc page.
2. **No caching of the home page at all.** `HomeView` recomputes sites, category counts,
   section/group counts, guide counts, featured docs, quick paths, and updates on every request.
3. **`HomePage.load()` runs on every request site-wide.** `context_processors.site_branding`
   (`context_processors.py:4-5`) calls `HomePage.load()` → `get_or_create(pk=1)`
   (`models.py:487-490`) for **every** page (doc pages included), adding a query to each request.
4. **N+1 queries in the template path.** `_featured` does `home.featured_sites.all()` then
   `fs.site` (one query per featured site, `views.py:98-100`); the template reads
   `u.site.slug/name/icon` per update (`home.html:317-324`) with `home.updates.all()` lacking
   `select_related` (`views.py:68`). `DocumentationSite` is fetched without `select_related`
   even though `.source` is read.
5. **Render-blocking Tailwind CDN.** Both `home.html:7` and `base.html:7` load
   `https://cdn.tailwindcss.com` synchronously in `<head>`. This is a frontend/perceived-load
   cost (large blocking script, no build step) shared by every page; see Out of Scope.

**Objective.** Make opening a document require at most one GitHub *tree* API call (usually
zero) instead of one content call per page, make the home page reuse the same cheap, shared
tree data (or a cached result) instead of rebuilding it per featured site, share caches across
all processes, and stop re-rendering unchanged documents.

**Success criteria (user-verified).**

- After a sync + index, opening a document triggers no per-page GitHub content requests.
- The home page serves from cache on repeat visits and triggers no per-page GitHub content
  requests; it does not build a fresh tree per featured site per request.
- Warm loads are fast and consistent across all uvicorn workers.
- A content sync invalidates and refreshes caches in every process.
- Nav labels/order, public/private filtering, prev/next, breadcrumbs, search, and MCP
  responses are unchanged.

## Components & Modules Involved

**New files**
- `apps/documentation/migrations/0013_documentationsearchdocument_nav_metadata.py`

**Files changed**
- `apps/documentation/models.py` — add nav-metadata fields to `DocumentationSearchDocument`.
- `apps/documentation/services/access.py` — add `label_and_order(metadata, fallback)`.
- `apps/documentation/services/structure.py` — accept a `page_meta` lookup in
  `build_structure_tree`; keep the `read_raw` fallback.
- `apps/documentation/services/documentation.py` — `page_meta_map()`, pass it into the tree
  build, cache rendered output in `document()`, add a `clear_home_cache()` helper.
- `apps/documentation/services/search.py` — persist nav metadata during `build_index`; do not
  cache an empty metadata map.
- `apps/documentation/services/sync.py` — invalidate after indexing (DB-cache friendly).
- `apps/documentation/management/commands/build_docs_index.py` — invalidate after indexing.
- `apps/documentation/views.py` — `HomeView` caching + `select_related`/`prefetch_related`;
  cache featured docs instead of rebuilding trees.
- `apps/documentation/context_processors.py` — use cached `HomePage`.
- `apps/documentation/admin.py` — invalidate home cache on `HomePage`/`DocumentationSite`
  changes.
- `config/settings.py` — switchable cache backend + render/home TTLs.
- `docker/entrypoint.sh`, `docker/worker.sh` — create the cache table after migrate.
- `docker-compose.yml`, `.env.sample` — cache backend env + table.
- `README.md` — document the shared cache and the required first-time reindex.

**Reused (unchanged behavior)**
- `DocumentationSearchDocument` table (one row per source+path, already rebuilt by
  `build_index` on sync and on admin upload).
- Sync pipeline: `sync_source` → `rebuild_structure_for_source` → `rebuild_index_for_source`.
- `build_docs_index` management command; MCP server (`mcp_server/scoping.py`).

## High-Level Implementation Steps (atomic)

1. **Model + migration.** Add to `DocumentationSearchDocument`
   (`models.py:235-275`), each field on its own line with a `verbose_name` and the closing
   `)` on its own aligned line (repo convention):
   - `nav_label = models.CharField(max_length=300, blank=True, verbose_name="nav label")`
   - `nav_order = models.IntegerField(null=True, blank=True, verbose_name="nav order")`
   - `access = models.CharField(max_length=20, default="public", verbose_name="access")`
   Generate migration `0013_documentationsearchdocument_nav_metadata.py`.

   *Success:* `python manage.py makemigrations --check` reports no missing migrations.

2. **Shared metadata helper.** In `services/access.py`, add
   `label_and_order(metadata, fallback) -> tuple[str, int | None]` containing the menu-name /
   position logic currently in `structure._page_label_and_order` (`MENU_KEYS`,
   `position` parsing). Reuse it from `structure.py` and `search.py` so parsing lives in one
   place. Keep the existing fallback semantics: `menu name` → `title` → `fallback`; order from
   `position`.

3. **Persist nav metadata at index time.** In `build_index` (`search.py:46-91`), after
   `metadata, body = parse_frontmatter(raw)`, compute `label, order = label_and_order(metadata,
   title)` and `access = meta_access(metadata)`, and set `nav_label`, `nav_order`, `access` on
   the `DocumentationSearchDocument.objects.create(...)` call (line 64). No extra fetch: the
   raw is already read in this loop.

4. **Use persisted metadata when building the tree.** Change `build_structure_tree`
   (`structure.py:48`) to accept `page_meta: dict[str, tuple[str, int | None, str]] | None =
   None`. In `pages_for` (lines 81-110):
   - If `page_meta` has the path → use `(label, order, access)`; apply the same anonymous
     private check (`if not authenticated and access == PRIVATE: continue`).
   - If the path is **absent** → keep the current `read_raw` + `_page_label_and_order` +
     `raw_access` fallback (guarantees correct privacy when the index is missing/stale).

5. **Expose the metadata map from the service.** In `DocumentationService`
   (`documentation.py`):
   - Add `self._page_meta_cache = None` in `__init__`.
   - Add `page_meta_map()`: read once via
     `DocumentationSearchDocument.objects.filter(source=self.source).values_list("path",
     "nav_label", "nav_order", "access")` (values_list avoids loading the large `content`
     column). Cache under `docs:source:{source.id}:pagemeta` with `DOCS_CACHE_TREE_TTL` **only
     when the mapping is non-empty** and `_use_cache` is true.
   - In `_tree` (line 89-123), pass `page_meta=(self.page_meta_map() if self._use_cache else
     None)` into `build_structure_tree`. Using `None` when caching is off preserves the current
     live-edit behavior for local dev (`DEBUG=1`, local filesystem) and S3-free setups.

6. **Cache rendered documents.** In `document()` (`documentation.py:201-229`), replace the
   unconditional `rendered = self.renderer.render(raw, path)` with:
   `key = self._key("render", path)`; `if self._use_cache: rendered = cache.get(key)`;
   on miss render and `cache.set(key, rendered, settings.DOCS_CACHE_RENDER_TTL)`. The cached
   value is the renderer's dict (`title`, `description`, `hidden`, `draft`, `html`,
   `headings`); breadcrumbs/prev/next/source URLs stay computed per request.

7. **Switch the cache backend.** In `config/settings.py` (replace the `CACHES` block at
   223-228):
   - Read `DOCS_CACHE_BACKEND` (default `locmem`) and `DOCS_CACHE_TABLE` (default
     `docs_cache_table`).
   - `db` → `django.core.cache.backends.db.DatabaseCache` with `LOCATION=DOCS_CACHE_TABLE` and
     `OPTIONS: {"MAX_ENTRIES": 10000}` (the default `MAX_ENTRIES=300` would cull tree/render
     entries).
   - otherwise → the existing `LocMemCache` (local dev unchanged).
   - Add `DOCS_CACHE_RENDER_TTL = int(os.environ.get("DOCS_CACHE_RENDER_TTL", "300"))`.
   - Add `DOCS_CACHE_HOME_TTL = int(os.environ.get("DOCS_CACHE_HOME_TTL", "300"))`.

8. **Make invalidation propagate.** `invalidate_source` (`sync.py:10-18`) already falls back to
   `cache.clear()` when the backend lacks `delete_pattern`; `DatabaseCache` has no
   `delete_pattern`, so `cache.clear()` runs. That now deletes the shared table and reaches all
   processes (both doc and home caches). Additionally:
   - In `rebuild_index_for_source` (`sync.py:21-25`), call `invalidate_source(source)` after the
     loop, so the metadata map cached (empty) during indexing is dropped and the next request
     rebuilds the tree from the freshly written rows.
   - In the `build_docs_index` command (`build_docs_index.py:14-22`), call `invalidate_source`
     for each indexed source afterward (same reason).

9. **Deployment wiring.**
   - `docker-compose.yml`: add `DOCS_CACHE_BACKEND: ${DOCS_CACHE_BACKEND:-db}` to the `web` and
     `worker` `environment` blocks.
   - `docker/entrypoint.sh` (after `migrate`) and `docker/worker.sh` (after `migrate`): add
     `python manage.py createcachetable`. With no arguments Django creates the table for the
     configured database cache from `LOCATION` and leaves existing tables untouched.
   - `.env.sample`: document `DOCS_CACHE_BACKEND=db`, `DOCS_CACHE_TABLE=docs_cache_table`,
     `DOCS_CACHE_RENDER_TTL=300`, `DOCS_CACHE_HOME_TTL=300`.

10. **Home: stop building a full tree per featured site.** In `_featured_docs`
    (`views.py:111-118`), cache the computed featured docs per scope under
    `docs:home:featured:{site.id}:{public|full}` with `DOCS_CACHE_HOME_TTL`, so the
    `DocumentationService.tree()` build (now cheap per steps 4-5, but still a remote tree call
    on a cold cache) runs at most once per TTL per featured site rather than once per request.
    Keep the existing `try/except → []` behavior on failure.

11. **Home: cache the page context per auth scope.** In `HomeView.get`, compute the context and
    store it under `docs:home:ctx:public` / `docs:home:ctx:full` (the only scope-dependent
    value is `featured`; key by scope to stay correct for logged-in vs anonymous visitors) with
    `DOCS_CACHE_HOME_TTL`. On a hit, render directly from the cached context. Invalidate via
    `clear_home_cache()` (step 13) and the sync `cache.clear()`.

12. **Home: fix N+1 and per-request loads.**
    - `DocumentationSite.objects.filter(enabled=True).select_related("source")` (`views.py:34`).
    - `_featured`: iterate `home.featured_sites.select_related("site")` (`views.py:98`).
    - updates: `home.updates.select_related("site")` (`views.py:68`) so the template's
      `u.site.*` accesses don't query per row (`home.html:317-324`).
    - Cache `HomePage.load()` (`models.py:487-490`) under `docs:home:page` with
      `DOCS_CACHE_HOME_TTL` so `context_processors.site_branding`
      (`context_processors.py:4-5`) stops issuing `get_or_create` on every request site-wide.

13. **Home: invalidate on admin changes.** Add a `clear_home_cache()` helper (module-level in
    `services/documentation.py`) that deletes `docs:home:page`, `docs:home:ctx:*`, and
    `docs:home:featured:*` (use `cache.delete` for the known keys; the shared backend has no
    `delete_pattern`, so clear the fixed keys explicitly, or `cache.clear()`). Call it from
    `HomePageAdmin.save_model`/`save_related` and `DocumentationSiteAdmin.save_model`/
    `delete_model`/`delete_queryset` (`admin.py`). Content sync already clears via
    `invalidate_source`.

14. **Optional (small, low risk).** Add `indexes` to `DocumentationNode.Meta` for
    `(site, enabled, type)` to speed the `structure_mode` / `build_structure_tree` queries
    (`models.py:399-402`, `structure.py:62-68`). Include only if desired; not required for the
    GitHub fix.

## Validation (user-run — the agent does not test)

1. `python manage.py migrate` (applies `0013`).
2. `python manage.py createcachetable` — confirm `docs_cache_table` exists.
3. `python manage.py build_docs_index` — confirm rows carry `nav_label`/`nav_order`/`access`
   (e.g. `DocumentationSearchDocument.objects.exclude(nav_label="").count()` > 0).
4. Open a GitHub-backed doc URL twice. On the second (warm) open, confirm no GitHub
   `/contents/...` requests occur (server logs / GitHub token usage) and the page renders.
5. Load the home page twice. Confirm the second load serves from cache and performs no
   per-page GitHub content requests, and that featured docs still list the expected pages for
   both an anonymous and a logged-in visitor.
6. Confirm sidebar labels, ordering, prev/next, breadcrumbs, and a private page hidden from an
   anonymous visitor behave as before.
7. Trigger a sync (admin **Sync documentation**) and confirm all workers reflect updated
   content (no stale cache from another worker); edit the `HomePage` in admin and confirm the
   home page updates.
8. Verify search and MCP (`get_navigation`, `get_document`) still return the same shapes.

## Risks / Notes

- **Privacy safety.** If a page has no indexed metadata row, `build_structure_tree` still reads
  the raw body and honors `access`, so anonymous visitors cannot see private pages. Do not
  remove that fallback.
- **First run after deploy.** Existing sources show the old (slow) behavior until one
  `build_docs_index`/sync populates nav metadata.
- **Home cache staleness.** Home and `HomePage` caches are invalidated on sync and on
  `HomePage`/`DocumentationSite`/branding admin saves; other admin edits (e.g. `FeaturedSite`
  inline ordering) are covered by `save_related` on `HomePage`. A short TTL (300 s) bounds any
  missed invalidation.
- **Two home cache variants.** Featured content differs for anonymous vs authenticated users,
  so the context is cached per scope; both keys are cleared together.
- **Blunt invalidation.** `DatabaseCache` has no `delete_pattern`, so each sync runs
  `cache.clear()` and rebuilds all sites' caches. Acceptable and rare (background job); revisit
  if a targeted invalidation backend is added later.
- **Extra DB queries.** Each cache `get`/`set` is a SQL round-trip. Keys are coarse (one tree
  key per scope, one metadata key per source, one render key per document, two home keys) to
  keep this low.
- **Config default.** `DOCS_CACHE_BACKEND` defaults to `locmem`; Docker/Coolify must set it to
  `db` (compose default does) to get the shared cache.
- **Model field convention** (repo rule) applied to the new fields and migration.
- No new Python dependency is required (Django's built-in database cache).

## Out of Scope

- Redis or any external cache service.
- Replacing the Tailwind CDN (`home.html:7`, `base.html:7`) with a build step or local bundle —
  a separate frontend/perceived-load change affecting all pages.
- Parallelizing the background sync's per-page fetches.
- Caching the GitHub provider tree separately / ETag-conditional requests.
- Reducing the number of `resolve_url_path`/`_is_private` tree lookups beyond what the cheaper
  tree build already achieves.
- Automatic reindex scheduling or file watchers.
- Agent-run testing.
