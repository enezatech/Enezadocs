# Planure: Slugified section/group segments in documentation URLs

## Feature Overview

Documentation URLs currently embed the **raw folder path**, so section/group folder
names leak into the address bar with percent-encoding:

- Today: `/docs/documention/Documention/Get%20Started/eneza-cli-developer-guide/`
- Wanted: `/docs/documention/documention/get-started/eneza-cli-developer-guide/`

**Business objective:** clean, human-readable, shareable URLs that use lowercase
kebab-case for section and group segments, while keeping the filesystem/provider
path unchanged.

**Problem being solved:** paths are used verbatim in URLs, so any folder with a
space, uppercase letter, or punctuation is percent-encoded (`Get%20Started`).
The provider still needs the real folder name to read files, so the two
representations must be mapped in both directions.

**Expected user outcome / success criteria**

- Section/group segments in every documentation URL are slugified
  (lowercased, non-alphanumerics collapsed to `-`), e.g. `Get Started` →
  `get-started`.
- The document leaf keeps its authored name (e.g. `eneza-cli-developer-guide`).
- Every generated link is slugified: sidebar nav, tabs, breadcrumbs,
  previous/next, in-page markdown links, site search results, and home page
  featured docs.
- Opening a slug URL serves the correct page (provider lookup still uses the
  real path).
- Old percent-encoded/raw-path URLs keep working (backward compatible).
- Assets (`/docs/<site>/assets/...`) and the MCP tool paths are unchanged.
- No model or migration changes.

> Scope note: the rule slugifies **every non-leaf path segment** (i.e. section
> and group folders). Document leaf names are left as authored. This matches the
> reported case and stays a pure function; a document that also has children is
> slugified only when it appears as a parent segment.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Slug rule | Slugify all path segments except the last (the document leaf). |
| Slug function | `django.utils.text.slugify` (already used by `create_mcp_token`). |
| Mapping direction on output | Pure function `slugify_path(real_path)` — no map needed. |
| Mapping direction on input | Build `{slug_path: real_path}` from the full tree; identity map keeps raw paths valid. |
| Where resolution happens | `DocumentationService.resolve_url_path()`, called by `DocumentationView.get`. |
| Markdown links | `LinkRewriteTreeprocessor` receives a `url_path` callable from the service. |
| Assets | Unchanged (not document paths). |
| MCP | Unchanged — tools keep exposing real paths. |
| Schema | None; no model fields, no migration. |
| Testing | User-run only; the agent does not test. |

## Components & modules involved

**Changed files**

- `apps/documentation/services/navigation.py`
  - Add `slugify_path(path)` — slugify every segment except the last.
- `apps/documentation/services/documentation.py`
  - `DocumentationService._url_map()` — cached `{slug_path: real_path}` from
    `full_flat_paths()`; identity entries first so raw paths still resolve.
  - `DocumentationService.resolve_url_path(url_path)` — map lookup with raw-path
    fallback.
  - `DocumentationService.slugify_path(path)` — delegate for callers/templates.
  - Pass a URL builder into `MarkdownRenderer`.
- `apps/documentation/services/markdown.py`
  - `MarkdownRenderer.__init__(self, site_slug, url_path=None)`; default to
    identity when not provided.
  - `LinkRewriteTreeprocessor` uses `url_path(resolved)` for `.md` links.
- `apps/documentation/templatetags/home_tags.py`
  - Add `doc_url` filter wrapping `slugify_path`, for path-based `href`s.
- `apps/documentation/templates/documentation/components/nav_tree.html`
  - `{{ node.path }}/` → `{{ node.path|doc_url }}/` (both anchor branches).
- `apps/documentation/templates/documentation/components/breadcrumbs.html`
  - `{{ crumb.path }}` → `{{ crumb.path|doc_url }}`.
- `apps/documentation/templates/documentation/components/prev_next.html`
  - `{{ document.previous.path }}` / `document.next.path` → `|doc_url`.
- `apps/documentation/templates/documentation/home.html`
  - `{{ d.path }}` → `{{ d.path|doc_url }}`.
- `apps/documentation/templates/documentation/404.html`
  - Show the slugified path in the message.
- `apps/documentation/views.py`
  - `DocumentationView.get` — resolve the request path to the real path before
    rendering; keep `current_path` as the real path for template comparisons.
  - `_structure_navigation` / `_folder_navigation` — slugify tab `url`s.
  - `SearchAllView` — add `url_path` to each result.
  - `SearchView` — add `url_path` to each result.
- `apps/documentation/static/documentation/js/search.js`
  - Use `it.url_path || it.path` for the result link and `data-search-nav`.

**Unchanged**
- `models.py`, `admin.py`, migrations, MCP server (`mcp_server/*`, `services/search.py`,
  `services/structure.py`, `services/filesystem.py`, `services/github.py`,
  `services/s3.py`).
- Asset URLs and image rewriting in markdown.

## High-level Implementation Steps

Each step is atomic, independently actionable, and lists the user's success check.

### 1. Add `slugify_path` to `navigation.py`
Pure helper: split on `/`, `django_slugify` every segment except the last,
`"/".join(...)`. Empty/blank path returns as-is.

**Success check:** a REPL call `slugify_path("Documention/Get Started/eneza-cli-developer-guide")`
returns `"documention/get-started/eneza-cli-developer-guide"`.

### 2. Add reverse resolution to `DocumentationService`
Add `_url_map()` (cached) built from `full_flat_paths()`: insert every real path
as its own key first, then `setdefault(slugify_path(path), path)`. Add
`resolve_url_path(url_path)` returning the mapped real path, else the raw value.
Add a thin `slugify_path()` delegate.

**Success check:** `resolve_url_path("documention/get-started/eneza-cli-developer-guide")`
returns the real path; the old `%20`-decoded raw path still returns itself.

### 3. Wire resolution into `DocumentationView.get`
After stripping the incoming `path`, set `path = service.resolve_url_path(path)`
before `_resolve_path`/`_is_private`/`service.document(path)`. All downstream
logic keeps using real paths.

**Success check:** navigating to the slug URL renders the page; the raw URL still
renders.

### 4. Slugify markdown link targets
Give `MarkdownRenderer` an optional `url_path` callable; in
`DocumentationService.__init__` pass `self.slugify_path`. Use it in
`LinkRewriteTreeprocessor._rewrite_link` for the rewritten `.md` URL (leave
`_rewrite_image` untouched).

**Success check:** a relative markdown link to a page inside `Get Started`
renders as `.../get-started/.../` (no `%20`).

### 5. Add the `doc_url` template filter
In `home_tags.py`, register `doc_url = slugify_path` as a filter.

**Success check:** `{% raw %}{{ "Documention/Get Started/eneza-cli-developer-guide"|doc_url }}{% endraw %}`
renders the slug path.

### 6. Update sidebar, breadcrumb, prev/next, home templates and 404
Apply `{% load home_tags %}` where missing and pipe the path through `doc_url`
in the anchors listed under "Components". Keep all `== current_path` comparisons
on the real path (unchanged).

**Success check:** hovering sidebar/tabs/breadcrumbs/prev-next on the sample page
shows slug URLs only.

### 7. Update `views.py` URL builders
Slugify tab `url`s in `_structure_navigation` and `_folder_navigation` (wrap the
computed path with `slugify_path`). Add `"url_path": slugify_path(item["path"])`
to each result in `SearchAllView` and `SearchView`.

**Success check:** tabs and the site-wide (`/search/`) JSON results expose slug
URLs.

### 8. Update `search.js`
Build the result link from `it.url_path || it.path` (keeps compatibility if the
field is absent).

**Success check:** search modal results link to slug URLs.

### 9. Documentation note
Append a short "As-built" note to the relevant change doc under
`docs/Developer/changes/`, recording the URL rule, the raw-path fallback, and the
MCP exception.

**Success check:** note exists and matches the shipped behavior.

## Validation (user-run — the agent does not test)

1. Run `python manage.py check` (no schema change, no migration).
2. Open `/docs/documention/Documention/Get%20Started/eneza-cli-developer-guide/`
   — still serves the page (raw fallback).
3. Open `/docs/documention/documention/get-started/eneza-cli-developer-guide/`
   — serves the same page.
4. Check sidebar, tabs, breadcrumbs, previous/next all use slug URLs.
5. Click an in-page markdown link that targets a page inside `Get Started` —
   lands on a slug URL.
6. Search (modal and page search) — results link to slug URLs.
7. Home page featured docs — links are slug URLs.
8. Assets still load from `/docs/<site>/assets/...`.
9. MCP `get_navigation` / `get_document` still return real paths and work
   unchanged.

## Risks / notes

- **Pure-function assumption**: slugifying every non-leaf segment also slugifies a
  document node that is a parent of other pages. Accepted v1; the reverse map
  resolves it.
- **Slug collisions**: two different folder names can slugify to the same value
  (e.g. `Get Started` vs `get-started`). Identity entries win; the second loses.
  Rare; no disambiguation in v1.
- **Full-tree cost**: `resolve_url_path` reads `full_flat_paths()`, already used
  by the private-content check, so no new provider hit pattern is introduced.
- **Cache timing**: the URL map is built per service instance (per request), so it
  is always consistent with the current tree.
- **MCP divergence**: MCP clients keep using real paths while the website uses
  slugs; the same document has two path forms. Documented as intentional.
- **Assets with spaces** are still percent-encoded; only document paths are
  slugified.
- Model edits are not involved; the repo field convention does not apply here.
- The user is solely responsible for all testing and validation of the output.

## Out of scope

- Slugifying asset/image URLs.
- Slugifying the MCP `get_navigation`/`get_document` path surface.
- Slug collision disambiguation or redirects from raw to slug URLs (301s).
- Renaming provider folders or `DocumentationNode.path`.
- Per-segment configurability (section-only vs all folders).
- Agent-run testing.
