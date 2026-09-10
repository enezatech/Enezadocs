# Django Markdown Documentation App — Implementation Plan

## Goal

Build a Django 6.1 (Python 3.13) documentation web application in `D:\projects\Enezadocs` that renders Markdown from **Local filesystem** and **GitHub** sources through one unified UI, reusing the existing `htmltemplate/` design system (Tailwind + OKLCH light/dark theme). Markdown files remain the source of truth; the database holds only configuration, sync state, and a search index.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Rendering | **Server-side** (Python Markdown → sanitized HTML → Django template). Template's CSS design system + interactive JS kept; its JS Markdown parser and `DOCS` array removed. |
| v1 scope | **Leaner**: Local + GitHub providers, caching, sync (admin action + management command), navigation, search, asset proxy, admin UI, template UI, auth+SSO. |
| Auth | **Django auth + django-allauth** (email login/signup + GitHub/Google SSO), wired to the template's `login.html`/`signup.html`. |
| Search | **Server-side index + endpoint** (`DocumentationSearchDocument` + `GET /docs/<slug>/search/?q=`) |
| Database | **SQLite** (PostgreSQL deferred). |
| Deferred | PostgreSQL, Celery/broker, GitHub webhooks, `DocumentationVersion`, extra providers (GitLab/Bitbucket/S3/HTTP), per-source token encryption. |
| Cache | Django cache framework, `locmem` in dev (Redis/memcached later); configurable TTLs. |
| Markdown | `markdown` + `python-frontmatter` + `Pygments` (code highlight) + `nh3` (sanitize). |
| GitHub API | `requests`; token from `GITHUB_TOKEN` env var only. |
| Tailwind | CDN in v1 (compiled build deferred). |

## Dependencies (`requirements.txt`)

```
Django~=6.1
markdown
python-frontmatter
Pygments
nh3
requests
django-allauth
Pillow
```

(Pillow only for the `DocumentationSite.logo` `ImageField`.)

## Project layout

```
D:\projects\Enezadocs\
├── manage.py
├── config/                          # project package
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py / asgi.py
├── apps/
│   └── documentation/
│       ├── apps.py, models.py, admin.py, urls.py, views.py, forms.py
│       ├── services/
│       │   ├── base.py              # provider protocol + DTOs
│       │   ├── factory.py           # get_provider(source)
│       │   ├── documentation.py     # DocumentationService
│       │   ├── filesystem.py        # LocalDocumentationProvider
│       │   ├── github.py            # GitHubDocumentationProvider + GitHubClient
│       │   ├── markdown.py          # MarkdownRenderer
│       │   ├── navigation.py        # tree/breadcrumbs/prev-next
│       │   ├── search.py            # index builder + query
│       │   └── assets.py            # asset proxy helper
│       ├── management/commands/
│       │   ├── sync_docs.py
│       │   ├── build_docs_index.py
│       │   └── validate_docs.py
│       ├── migrations/
│       ├── templates/documentation/
│       │   ├── base.html, document.html, 404.html, site_index.html
│       │   └── components/ (header, sidebar, breadcrumbs, toc, prev_next, search_modal)
│       └── static/documentation/
│           ├── css/documentation.css   # extracted from template <style>
│           └── js/ (documentation.js, theme.js, navigation.js, search.js, toc.js, copy.js)
└── templates/                       # allauth overrides
    └── account/ (login.html, signup.html)
```

## Ordered tasks

### Phase 0 — Scaffold
1. Create project package `config/` (`django-admin startproject config .`) and `apps/` + `apps/documentation` app (`startapp`).
2. Write `requirements.txt`; install into `env/` (Django 6.1, allauth, markdown, python-frontmatter, Pygments, nh3, requests, Pillow).
3. Configure `settings.py`: add `documentation`, `allauth`, `allauth.account`, `allauth.socialaccount`, `socialaccount.providers.github`, `socialaccount.providers.google` to `INSTALLED_APPS`; add `allauth.account.auth_backends.AuthenticationBackend` to `AUTHENTICATION_BACKENDS`; set `SITE_ID=1`, `TEMPLATES`, `STATIC_URL`, `MEDIA_URL/MEDIA_ROOT`, `LOGIN_REDIRECT_URL`, cache config, and docs settings (`DOCS_CACHE_TREE_TTL=300`, `DOCS_CACHE_DOCUMENT_TTL=300`, `GITHUB_TOKEN` read from env).

### Phase 1 — Models (`apps/documentation/models.py`)
Follow the repo rule for **every** field: one field per line, `verbose_name` on every field, closing `)` on its own line aligned with the field start.
4. `DocumentationSource` — `name`, `source_type` (`TextChoices` LOCAL/GITHUB), `enabled`, `created_at`, `updated_at`, plus status fields `last_sync_status`, `last_sync_error`, `last_sync_at`.
5. `LocalDocumentationSource` — `OneToOneField(DocumentationSource, related_name="local")`, `root_path`.
6. `GitHubDocumentationSource` — `OneToOneField(DocumentationSource, related_name="github")`, `owner`, `repository`, `branch` (default `main`), `root_path` (default `docs`), `last_sync_at`, `last_commit_sha`, `enabled`.
7. `DocumentationSite` — `name`, `slug` (unique), `description`, `source` FK→`DocumentationSource` (PROTECT), `logo` ImageField, `enabled`, `created_at`, `updated_at`.
8. `DocumentationSearchDocument` — `source` FK (CASCADE), `path`, `title`, `description`, `content`, `updated_at`.
9. `makemigrations` + `migrate` (run by implementer; verification deferred to user).

### Phase 2 — Services
10. `services/base.py` — `DocumentationProvider` protocol: `get_tree()`, `get_document(path)`, `exists(path)`, `get_asset(path)`, `get_source_url(path)`, `get_edit_url(path)`. Dataclasses `DocumentationDocument` (title, path, content, html, description, headings, breadcrumbs, previous, next, source_url, edit_url) and a normalized tree node dict shape (title/type/children/path).
11. `services/factory.py` — `get_provider(source)` returns `LocalDocumentationProvider` or `GitHubDocumentationProvider` by `source_type`.
12. `services/filesystem.py` — `LocalDocumentationProvider`: `os.walk` scan of `root_path` for `.md`; **path-traversal guard** — resolve+normalize, reject `..` and reject any path outside `root_path`; `get_asset` reads files with content-type guess.
13. `services/github.py` — `GitHubClient` (GET trees recursive, raw file via contents API, latest commit sha, `Authorization` header only when `GITHUB_TOKEN` set) + `GitHubDocumentationProvider` using it; cache tree/document/asset via `cache` keys `docs:github:<source_id>:tree|document:<path>|asset:<path>`.
14. `services/markdown.py` — `MarkdownRenderer`: parse YAML frontmatter (`python-frontmatter`) → title/description/order/hidden/draft; render with `markdown` (extensions: `extra`, `toc`, `sane_lists`, `attr_list`); custom extension to convert `> [!NOTE]`/`TIP`/`IMPORTANT`/`WARNING`/`CAUTION` into the template's `.callout` markup; rewrite relative `.md` links → `/docs/<slug>/<path>/` and relative image srcs → `/docs/<slug>/assets/<path>`; wrap fenced code as `.codeblock` (lang label + copy button) with Pygments highlighting; add heading IDs; sanitize final HTML with `nh3` (allowlist); return headings for TOC.
15. `services/navigation.py` — build normalized tree (folders/documents), flat ordered list, breadcrumbs, prev/next; skip `hidden`/`draft` docs; honor `order` from frontmatter.
16. `services/documentation.py` — `DocumentationService`: `tree()`, `document(path)`, `navigation(path)`, `search(query)`, `asset(path)`; resolves provider via factory and applies caching; `document()` returns a `DocumentationDocument` DTO.
17. `services/search.py` — `build_index(site)` (strip markdown to plain text, store per document) and `query(site, q)` (ranked substring match on title/description/content).

### Phase 3 — Views + URLs
18. `views.py` — thin views: `SiteIndexView` (`/docs/`, lists enabled sites), `DocumentationView` (site_slug, path — delegates entirely to service; renders `documentation/document.html`), `SearchView` (JSON), `AssetProxyView` (streams provider asset with correct content-type). Return `404` template when document missing.
19. `urls.py` — `/docs/`, `/docs/<slug>/`, `/docs/<slug>/<path:path>/`, `/docs/<slug>/assets/<path:path>/`, `/docs/<slug>/search/`. Include app urls + `allauth` in `config/urls.py`.

### Phase 4 — Templates (convert `htmltemplate/`)
20. Extract the `<style>` block into `static/documentation/css/documentation.css`; move no-FOUC theme script, tailwind config, and interactivity JS into `static/documentation/js/` (`theme.js`, `navigation.js`, `search.js`, `toc.js`, `copy.js`, `documentation.js`). Remove the JS Markdown parser, `DOCS` array, and hash router.
21. `templates/documentation/base.html` — shared `<head>`, header, three-column layout (sidebar / content / TOC), search modal, drawer, toast.
22. `components/` — `sidebar.html` (server-rendered nav tree with collapsible groups), `breadcrumbs.html`, `toc.html` (from DTO `headings`), `prev_next.html`, `search_modal.html` (calls `/docs/<slug>/search/`), `header.html` (version menu removed; GitHub link when source is GitHub; auth link reflects `request.user`).
23. `document.html`, `site_index.html`, `404.html` — render DTO (`document.html|safe`) + nav + toc + prev/next + breadcrumbs + title.

### Phase 5 — Admin + management commands + sync
24. `admin.py` — register `DocumentationSite`, `DocumentationSource` with inlines for local/github config; show `owner/repository/branch/root`, `last_commit_sha`, `last_sync_status/error/at`; add admin action **Sync documentation**.
25. `management/commands/sync_docs.py` — for each enabled GitHub source: fetch latest commit sha; if changed, invalidate tree/document caches, rebuild search index, update `last_commit_sha`/`last_sync_at`/`last_sync_status`; set error status on failure.
26. `management/commands/build_docs_index.py` — rebuild `DocumentationSearchDocument` for all/specified sites.
27. `management/commands/validate_docs.py` — report count of files, nav entries, broken internal links, missing images, invalid frontmatter, duplicate paths.

### Phase 6 — Auth + SSO
28. Configure `SOCIALACCOUNT_PROVIDERS` (GitHub scope, Google) and read client id/secret from env (`GITHUB_CLIENT_ID`, `GITHUB_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_SECRET`).
29. Override `templates/account/login.html` and `templates/account/signup.html` to match the template's styled pages, including GitHub/Google SSO buttons (`{% provider_login_url %}`) and email/password forms.

### Phase 7 — Wiring + assets
30. Wire header auth state to `request.user` (Sign in / Sign out) and remove the localStorage mock auth from the converted JS.
31. Ensure relative images resolve through `AssetProxyView` (cached; offline fallback served from cache).

## Model field conventions (enforced)

Every model field: own line, includes `verbose_name`, and multi-line field declarations close the `)` on its own line aligned with the field start. Example:

```python
source = models.OneToOneField(
    DocumentationSource,
    on_delete=models.CASCADE,
    related_name="local",
    verbose_name="source",
)
```

## Key risks / notes

- **GitHub rate limits**: mitigate via cache TTLs + `last_commit_sha` change detection; never make per-UI-component API calls.
- **Path traversal**: normalize/validate all paths against configured root; reject `..` and absolute paths.
- **Token secrecy**: `GITHUB_TOKEN` only via env; never in HTML/URLs/logs/JS.
- **Offline**: provider returns cached document when GitHub is unavailable (optional "documentation may be out of date" notice).
- **Pygments vs template CSS**: Pygments classes differ from the template's `.token-*` classes — include a Pygments stylesheet adapted to the theme variables.
- **allauth SSO** requires real OAuth app credentials (GitHub/Google); email login/signup works without them.

## Validation (user-run — agent does not test)

1. `manage.py migrate`, `manage.py createsuperuser`, `manage.py runserver`.
2. Create a `LocalDocumentationSource` pointing at a sample `docs/` folder + a `DocumentationSite`; open `/docs/<slug>/`.
3. Create a `GitHubDocumentationSource` (public repo), run `sync_docs`, verify docs render, asset proxy, and search.
4. Run `build_docs_index` and `validate_docs`.
5. Verify email login/signup; configure OAuth apps and verify GitHub/Google SSO.
6. Verify offline behavior (temporarily disable network → cached docs still serve).

## Open questions (non-blocking)

- None. Default document for a site (`index.md`) and site listing page behavior assumed; adjust per preference during implementation.
