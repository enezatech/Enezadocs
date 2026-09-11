# Planure: Public/Private Content Visibility (signed-in only)

## Feature Overview

Let documentation authors mark **some content as private** so it is visible only to
signed-in (authenticated) users, while the rest stays public. Two settings exist and
are combined with a most-restrictive-wins rule:

1. **Section / Group access** — a choice on every `DocumentationNode` row
   (`section`/`group`): `public` (everyone) or `private` (authenticated only).
2. **Markdown page access** — the same property as YAML frontmatter on `.md` files:
   `access: public` (default when absent) or `access: private`.

Success criteria: anonymous users see/have no access to private content anywhere
(nav, tabs, sidebar, prev/next, landing, search) and direct private URLs redirect to
sign-in; authenticated users see everything.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Access model | **public** (everyone) and **private** (any authenticated user) only. |
| DB field | `DocumentationNode.access` (`TextChoices` `public`/`private`, default `public`). Applies to both `section` and `group` rows. |
| Markdown key | `access: public` / `access: private` (case-insensitive); absent ⇒ `public`. |
| Inheritance | **Most-restrictive wins** (private node gates its subtree; page private if ancestor node private or own frontmatter private). |
| Anonymous nav | Private items are **hidden**; folders/groups left empty after filtering are dropped. |
| Direct URL (anon) | **Redirect to sign-in** (`/accounts/login/?next=<url>`); missing paths keep 404. |
| Search | Index keeps all docs; results intersected with the requester's visible paths at query time. |
| Tree cache | Per visibility scope: `docs:site:<id>:tree:<scope>` (`full`/`public`). |
| Non-structure mode | Only per-page `access:` gating applies (no DB nodes to hold folder access). |
| Admin | `access` filterable/editable on the `DocumentationNode` changelist + form. |
| Rebuild impact | `import_structure` / admin import recreates nodes → default back to `public`. |
| Content samples | Sample `.md` files are not modified by this change. |

## Components & modules involved

**Files changed**
- `apps/documentation/models.py` — `DocumentationNode.AccessLevel` + `access` field.
- `apps/documentation/migrations/0004_documentationnode_access.py` — migration (generated).
- `apps/documentation/services/access.py` — NEW: `normalize`, `meta_access`, `raw_access`, `filter_public_documents`.
- `apps/documentation/services/structure.py` — auth-aware tree builder (`authenticated`, inherited-private pruning, per-page frontmatter gating, empty-node dropping).
- `apps/documentation/services/documentation.py` — `DocumentationService(site, authenticated=True)`, scoped `tree()`/`full_tree()` caching, `full_flat_paths()`, auto-mode public filter, auth-scoped `search()`.
- `apps/documentation/services/search.py` — `query_documents(..., allowed_paths=None)`.
- `apps/documentation/views.py` — pass `request.user.is_authenticated`; `_is_private` gate + login redirect.
- `apps/documentation/admin.py` — `access` in list_display/list_filter/list_editable.
- `apps/documentation/services/sync.py` — invalidate `docs:site:<id>:tree:*` (both scopes).

**Unchanged** — providers, markdown renderer, templates, navigation primitives, asset
proxy, `DocumentationSearchDocument`, sample markdown content.

## Implementation steps

1. **models.py** — add `AccessLevel(PUBLIC/PRIVATE)` and `access` CharField
   (own line, `verbose_name`, aligned close paren, default `public`).
2. **Migration** — `makemigrations documentation` → `0004_documentationnode_access.py`.
3. **services/access.py** — normalize frontmatter access values; parse metadata/raw;
   non-mutating tree filter dropping private documents and emptied folders.
4. **structure.py** — `build_structure_tree(..., authenticated=True)`; prune private
   node subtrees for anonymous; drop private pages in `pages_for`; drop nodes that end
   up empty for anonymous.
5. **documentation.py** — per-scope tree caching (`full`/`public`); `full_tree()`,
   `full_flat_paths()`; auto-mode filter via `filter_public_documents`; `search()`
   passes `allowed_paths` for anonymous.
6. **sync.py** — `cache.delete_pattern("docs:site:<id>:tree:*")` replaces exact-key
   delete.
7. **search.py** — `allowed_paths` param filters out-of-scope results.
8. **views.py** — construct services with the auth flag; `_is_private` + redirect to
   `account_login?next=...`; `SearchView` auth-aware.
9. **admin.py** — expose `access` on changelist (display/filter/list_editable).

## Validation (user-run — agent does not test)

1. `python manage.py migrate` (applies `0004_*`).
2. Admin: mark a section/group `access=private`; verify filter + list_editable.
3. Add `access: private` to one sample page frontmatter.
4. Anonymous: private items vanish from tabs/sidebar/search; direct URL → sign-in,
   returns to page after login.
5. Authenticated: private content renders; search returns it.
6. Fully-private site root → sign-in redirect for anonymous.
7. After a sync/file change, both tree scopes refresh (no stale private entries).
8. `validate_docs` still reports the full file set (index/build operate on full tree).

## Risks / notes

- Re-importing structure resets node `access` to `public`.
- Per-scope tree cache keys require wildcard invalidation (`tree:*`).
- Asset proxy is not access-gated (guessed asset URLs still serve) — accepted v1
  trade-off.
- `DocumentationService` defaults `authenticated=True`; views must pass the flag.

## Out of scope

- Per-user/per-role permissions; lock-badge UI; asset gating; preserving access on
  structure re-import; site-level visibility; agent testing.
