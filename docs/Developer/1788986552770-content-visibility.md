
---
menu name: Public/Private Content Visibility 
position: 6
---

# Plan: Public/Private Content Visibility (signed-in only)

> Note: Project grobal rules ask for the final planure to live in
> `feature_Planure/feature_Planure_content_visibility.md`. This planning session's
> write permissions only allow the default plans directory, so this file is the
> authoritative plan. Copy it into `feature_Planure/` (or have the implementation
> agent persist it there) once permissions allow.

## Goal

Let documentation authors mark **some content as private** so it is visible only to
signed-in (authenticated) users, while the rest stays public. Two settings exist and
are combined with a most-restrictive-wins rule:

1. **Section / Group access** — a choice on every `DocumentationNode` row
   (`section`/`group`): `public` (everyone) or `private` (authenticated only).
2. **Markdown page access** — the same property as YAML frontmatter on `.md` files:
   `access: public` (default when absent) or `access: private`.

Private content is **hidden from anonymous users** in the nav tree, section tabs,
sidebar, prev/next links, landing-page resolution, and search results. An anonymous
user who directly opens a private URL is **redirected to the sign-in page**
(`/accounts/login/?next=<url>`) and returned to the page after login. Missing pages
still return the existing 404.

## Locked decisions

| Decision                         | Choice                                                                                                                                                                                                |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Access model                     | Two categories only: **public** (everyone) and **private** (any authenticated user). No per-user/role gating in this feature.                                                                         |
| DB field                         | `DocumentationNode.access` (`TextChoices`: `public`/`private`, default `public`). Applies to BOTH `section` and `group` rows.                                                                         |
| Markdown key                     | Frontmatter `access: public` / `access: private` (case-insensitive). Absent/unknown ⇒ `public`. No synonym keys.                                                                                      |
| Inheritance                      | **Most-restrictive wins**: a private section/group gates its whole subtree; a page is private if any ancestor node is private OR its own frontmatter is `access: private`.                            |
| Anonymous nav                    | Private sections/groups/pages are **hidden** (not shown with locks). Empty folders/groups after filtering are dropped so no shell tabs/groups render.                                                 |
| Direct URL (anon)                | **Redirect to sign-in** (`account_login`) with `?next=` so the user returns after auth. Truly missing pages keep returning 404.                                                                       |
| Search                           | Server-side search index keeps all docs; results are intersected with the requester's visible paths at query time. No new column on `DocumentationSearchDocument`.                                    |
| Tree caching                     | Cache the tree **per visibility scope** — `full` vs `public` — under `docs:site:<id>:tree:<scope>` (two variants max, because private = any authenticated user).                                      |
| Non-structure (auto folder) mode | No DB section/group rows exist, so only **per-page** `access:` frontmatter gating applies. Folder-level privacy is available only via `DocumentationNode` rows (structure mode / admin).              |
| Admin UI                         | `access` visible/editable on the `DocumentationNode` changelist and form (filter + list_editable).                                                                                                    |
| Rebuild impact                   | `import_structure` / admin "Import structure" deletes and recreates nodes; re-imported nodes default back to `public`. Preserving prior settings on rebuild is **out of scope** (warned to the user). |
| Content samples                  | Do NOT modify existing sample `.md` bodies/frontmatter during implementation. Marking a sample doc `access: private` is part of user validation.                                                      |

## Components & modules involved

**Files to change**
- `apps/documentation/models.py` — `DocumentationNode.access` field + `AccessLevel`.
- `apps/documentation/migrations/0004_documentationnode_access.py` — new migration (generated).
- `apps/documentation/services/access.py` — NEW: access helpers (normalize / meta / raw / prune).
- `apps/documentation/services/structure.py` — auth-aware tree builder + filtering.
- `apps/documentation/services/documentation.py` — `authenticated` flag, scoped tree caches, `full_tree()`.
- `apps/documentation/services/search.py` — intersect results with visible paths.
- `apps/documentation/views.py` — pass `request.user.is_authenticated`; gate private URLs.
- `apps/documentation/admin.py` — expose `access` on `DocumentationNode` admin.
- `apps/documentation/services/sync.py` — invalidate `tree:*` scope keys.

**Unchanged**
- Providers (`filesystem.py`, `github.py`, `factory.py`), markdown renderer internals,
  templates, navigation primitives, assets proxy, `DocumentationSearchDocument` model.

## High-level implementation steps (atomic, ordered)

### 1. Add the model field
- 1.1 In `DocumentationNode` add `class AccessLevel(models.TextChoices)` with
  `PUBLIC = "public", "Public"` and `PRIVATE = "private", "Private"`.
- 1.2 Add the field (own line, with `verbose_name`, aligned closing paren):

```python
    access = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.PUBLIC,
        verbose_name="access",
        help_text="Public = everyone; Private = signed-in users only.",
    )
```
- 1.3 Success criteria: field follows the repo field convention; default is `public`;
  existing DB rows migrate cleanly.

### 2. Generate the migration
- 2.1 Run `python manage.py makemigrations documentation` → creates `0004_*`.
- 2.2 Do NOT run `migrate` (user applies it during validation).
- 2.3 Success criteria: migration adds the column with default `"public"`.

### 3. Create access helpers (`services/access.py`, new file)
- 3.1 Constants `PUBLIC = "public"`, `PRIVATE = "private"`.
- 3.2 `normalize(value) -> str` — lower/strip; return `PRIVATE` for any private-ish
  value (`private`, `true`), else `PUBLIC`.
- 3.3 `meta_access(metadata: dict) -> str` — read key `access`; default `PUBLIC`.
- 3.4 `raw_access(raw: str | None) -> str` — parse frontmatter tolerantly, return `meta_access`.
- 3.5 Tree-filter helper `prune_documents(nodes, is_private_pred)` returns a **new**
  tree (use `dataclasses.replace`) removing private `document` nodes and dropping
  folder nodes that become empty.
- 3.6 Success criteria: helpers are pure functions with no eager model imports.

### 4. Auth-aware tree builder (`services/structure.py`)
- 4.1 `build_structure_tree(site, provider_tree, read_raw, authenticated=True)`.
- 4.2 In `convert`, thread an `inherited_private` flag down the row recursion:
  - effective private for a row = `inherited_private or row.access == PRIVATE`.
  - if effective private AND not `authenticated` → skip the entire row subtree
    (do not add the node or call `pages_for` for it).
- 4.3 In `pages_for(folder)`, keep the existing single `read_raw` per doc and also
  read its `access`: drop the page when `not authenticated` and its frontmatter is
  `private`.
- 4.4 4.2–4.3 implement the "most-restrictive wins" rule without ancestor lookups.
- 4.5 Success criteria: anon tree excludes private nodes and private pages inside
  public nodes; auth tree is unchanged from today.

### 5. Non-structure (auto folder) filtering
- 5.1 Reuse the tree-building path: get the full provider tree, then if
  `not authenticated`, apply `prune_documents` using `raw_access(self.get_raw(path))`
  for every `document` node; drop folders left empty.
- 5.2 Do not mutate the cached full tree: build new nodes with `dataclasses.replace`.
- 5.3 Success criteria: anon nav drops private pages and any folder that only
  contained private pages.

### 6. Scoped trees + auth flag (`services/documentation.py`)
- 6.1 `DocumentationService.__init__(self, site, authenticated=True)`. Default
  `True` keeps internal callers (commands, sync, admin) on the **full** tree.
- 6.2 Replace `tree()` internals: cache key `docs:site:<id>:tree:<scope>` where
  `scope = "full"` when authenticated else `"public"`. Builder receives the flag
  (steps 4/5).
- 6.3 Add `full_tree()` (== `tree()` with `authenticated=True` scope) and
  `full_flat_paths()`; keep `flat_paths()`/`nav_tree()` scoped as today.
- 6.4 `search()` forwards the scoped visible-path set to the query layer.
- 6.5 Success criteria: anonymous requests never read a private page through any
  scoped helper; both scopes are cached separately and independently invalidated.

### 7. Cache invalidation (`services/sync.py`)
- 7.1 In `_invalidate`, replace the exact `cache.delete(f"...:tree")` with
  `cache.delete_pattern(f"docs:site:{site.id}:tree:*")`.
- 7.2 Success criteria: a sync clears both `full` and `public` tree variants.

### 8. Search scoping (`services/search.py`)
- 8.1 `query_documents(source, query, allowed_paths=None)` — compute scores exactly
  as today, then drop results whose `path` is not in `allowed_paths` when provided.
- 8.2 Search view passes `allowed_paths = {flatten(service.tree()) paths}` (scoped).
- 8.3 Success criteria: anonymous search cannot return private titles/paths;
  authenticated search unchanged; empty query still returns `[]`.

### 9. Views: auth flag + private-URL gate (`views.py`)
- 9.1 `DocumentationView.get` builds `DocumentationService(site,
  authenticated=request.user.is_authenticated)`.
- 9.2 Resolve/landing logic keeps using the scoped tree (public for anon).
- 9.3 New gate after resolution, for anonymous users only:
  - if target path ∈ full paths but ∉ public paths → redirect to login:
    `redirect(reverse("account_login") + "?next=" + quote(request.get_full_path()))`.
  - special case: scoped flat is empty, full flat is non-empty (fully-private site)
    → same login redirect instead of 404.
  - otherwise → existing 404 / document rendering unchanged.
- 9.4 `SearchView.get` constructs the service with the authenticated flag.
- 9.5 `SiteIndexView` and `AssetProxyView` unchanged.
- 9.6 Success criteria: anonymous can never render private content; a stale link to
  private content sends them to sign-in and back; missing paths still 404.

### 10. Admin exposure (`admin.py`)
- 10.1 `DocumentationNodeAdmin`: add `access` to `list_display`,
  `list_filter = ("site", "type", "enabled", "access")`,
  `list_editable = ("order", "enabled", "access")`.
- 10.2 Success criteria: admin changelist filters/edits access without form override.

### 11. Documentation of behavior (no source content edits)
- 11.1 Note in docs: folder-level privacy requires a section/group node (structure
  mode/admin); pure filesystem sites gate per file only.
- 11.2 Do not edit any `docs/**/*.md` frontmatter in this change.
- 11.3 Success criteria: reviewers know exactly which knob applies where.

## Risks / notes

- **Rebuild wipes access**: "Import navigation structure from provider"
  (`import_structure`, admin action) deletes and recreates nodes → new rows default
  to `public`. Preserving per-node privacy across rebuilds is out of scope; warn in
  admin help text / planure.
- **Raw-doc reads**: filtering pages by frontmatter needs one raw read per page while
  building the anonymous (public) tree in auto-folder mode and in structure mode
  (structure mode already reads every page for labels). Mitigated by per-scope tree
  caching (`docs:site:<id>:tree:public`).
- **Cache keys**: any code that invalidates `docs:site:<id>:tree` must use the
  wildcard form (`delete_pattern("docs:site:<id>:tree:*")`) or stale private content
  lingers for up to the TTL.
- **Assets inside private pages**: asset proxy is not gated in this feature; an
  authenticated user never sees a private page anonymously, but a guessed asset URL
  is still served. Acceptable v1 trade-off; document as a follow-up.
- **`authenticated=True` default** on `DocumentationService` protects non-view
  callers (sync/index/validate) but means any future view that forgets to pass the
  flag would default to full content — keep views explicit.
- Model edits must follow the repo field convention (own line, `verbose_name`,
  aligned closing parenthesis) enforced by grobal rules.

## Validation (user-run — agent does not test)

1. `python manage.py makemigrations documentation` then `python manage.py migrate`
   (migration `0004_*` applies).
2. In admin: set one **section** (or a nested group) to `access=private`; confirm it
   appears with the filter and list_editable.
3. Add `access: private` to the frontmatter of one public sample page
   (e.g. `docs/Developer/eneza-cli-developer-guide.md`).
4. **Anonymous**: the private section/page disappear from tabs, sidebar, and search;
   opening `/docs/<slug>/<private page>/` directly redirects to the sign-in page and
   returns to the page after logging in.
5. A public page whose private sibling was removed must not appear in prev/next;
   breadcrumbs/landing redirect skip private content.
6. **Authenticated**: the private section/page appears and renders normally; search
   returns it.
7. Fully-private site (all sections private): anonymous visits `/docs/<slug>/` and is
   redirected to sign-in; after login the site opens normally.
8. Run `sync_docs` (GitHub source) or edit a file and confirm the `public` tree cache
   refresh clears both scopes (no stale private entries linger ≤ TTL).
9. `validate_docs` still reports the full file set (private included) — index/build
   commands operate on the full tree.

## Out of scope

- Per-user / per-role / group permissions (only "any authenticated user").
- Lock-badge UI for anonymous users (they see nothing private).
- Asset (image) access control.
- Preserving `access` across structure re-imports.
- Site-level access control (`DocumentationSite` visibility).
- Testing by the agent.
