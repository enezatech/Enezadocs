# Plan: GitBook-style Section Tabs + Sidebar Groups + Nested Pages

## Goal

For a single `DocumentationSite`, turn the folder layout in the source repo into a GitBook-style structure:
- **Top-level folders** → **horizontal Section tabs** (the `data-gb-sections` tabs in the reference).
- **Sub-folders** inside a tab → **collapsible sidebar Groups**.
- **Documents** inside a group → sidebar Pages.
- A Page may also have **nested sub-pages** (e.g. `Content structure` → `Sections`/`Groups`/`Pages`).

The Markdown files remain the source of truth; the DB is unchanged by this feature.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Structure source | **Folder-layout derived** (top-level folder = tab; depth 2+ = sidebar groups / nested pages). |
| Ordering & titles | **Numeric filename prefixes** (e.g. `0100-quickstart.md`) drive sort order and are stripped from displayed titles. Zero extra file reads → GitHub-rate-limit friendly. |
| Page-with-children | A document node may also carry `children`. File convention: a `.md` at `X` plus a folder `X/` with sub-pages merge into one expandable page node `X`. |
| Tab style | Keep the app's existing tab component (`base.html` `{% if tabs %}` nav, `border-b-2` underline) — do **not** copy GitBook's utility classes. |
| Provider-agnostic | Only the shared tree builder + templates change; both `LocalDocumentationProvider` and `GitHubDocumentationProvider` go through `build_tree_from_paths`. |
| Hidden/draft skip | **Out of scope** in this pass (it would require per-doc reads that hurt GitHub). Leave existing behavior as-is. |

## Files to change

- `apps/documentation/services/base.py` — add `order` to `NavigationNode`.
- `apps/documentation/services/navigation.py` — numeric prefix parsing; rewrite `build_tree_from_paths` (merge doc+same-path folder, sort by `order`); update `title_from_name`.
- `apps/documentation/views.py` — expose `current_path` for expandable page auto-open; extend `_open_paths`.
- `apps/documentation/templates/documentation/components/nav_tree.html` — add a **page-with-children** case.
- `apps/documentation/static/documentation/css/documentation.css` — styles for the expandable page node.
- `apps/documentation/static/documentation/js/navigation.js` — extend the group-toggle selector to page-level links.

## Ordered tasks

### 1. Model: `services/base.py`
Add an order field to `NavigationNode` (keep everything else):

```python
@dataclass
class NavigationNode:
    title: str
    path: str = ""
    type: str = "document"
    order: int | None = None
    children: list["NavigationNode"] = field(default_factory=list)
```
`to_dict()` should include `order` (optional; harmless if omitted, but include for completeness).

### 2. Numeric prefix helpers: `services/navigation.py`
Add a regex + parser reused for folders and files:

```python
import re
_ORDER_RE = re.compile(r"^(\d+)[._-]*(.*)$")

def split_order(name: str) -> tuple[int | None, str]:
    m = _ORDER_RE.match(name)
    if m:
        return int(m.group(1)), (m.group(2).strip("-_") or name)
    return None, name

def clean_title(name: str) -> str:
    order_val, rest = split_order(name)
    return (rest.replace("-", " ").replace("_", " ").strip().title()) or name

def sort_key(node) -> tuple:
    return (node.order if node.order is not None else 1_000_000,
            node.title.lower(),
            node.path)
```
Update `title_from_name` to delegate to `clean_title` (so breadcrumbs / fallback titles / tab titles reliably strip the prefix).

### 3. Build tree with merge + sort: `services/navigation.py`
Rewrite `build_tree_from_paths` to build a raw tree, then (a) merge a document node with a same-path folder node and (b) recursively sort children:

```python
def build_tree_from_paths(paths):
    root = NavigationNode(title="", path="", type="folder")
    for raw in paths:
        parts = [p for p in raw.split("/") if p]
        if not parts:
            continue
        _insert(root, parts)
    _merge_and_sort(root)
    return root.children

def _merge_and_sort(node):
    by_path: dict[str, list[NavigationNode]] = {}
    for child in node.children:
        by_path.setdefault(child.path, []).append(child)
    merged: list[NavigationNode] = []
    for _path, group in by_path.items():
        doc = next((c for c in group if c.type == "document"), None)
        folder = next((c for c in group if c.type == "folder"), None)
        if doc is not None and folder is not None:
            doc.children = folder.children
            merged.append(doc)
        else:
            merged.extend(group)
    for child in merged:
        _merge_and_sort(child)
        child.children.sort(key=sort_key)
    node.children = sorted(merged, key=sort_key)
```
`_insert` builds folder + document nodes from `split_order` so each node gets `order` and a clean `title` (set `order=int_val, title=clean_title(stem)`).

`flatten`, `find_node`, `first_document` already recurse `children`, so they continue to work: a page-with-children is still a `document` (appended in `flatten`) with its sub-pages following it.

### 4. Route active branch: `views.py`
- Pass `current_path` into the sidebar context (already present via `context["current_path"]`).
- Extend `_open_paths` (and the template's open condition) so an expandable **page** opens both when it's an ancestor of the current path **and** when it is the current page:

```python
def _open_paths(self, path):
    parts = [p for p in path.split("/") if p]
    result, acc = [], []
    for part in parts[:-1]:
        acc.append(part)
        result.append("/".join(acc))
    return result
```
In the template, treat a page node as `open` when `node.path in open_paths or node.path == current_path`.

### 5. Sidebar template: `components/nav_tree.html`
Render three cases:
- `node.type == 'folder'` → collapsible group (unchanged).
- `node.type == 'document' and node.children` → **expandable page**: an `<a class="nav-page-link">` (so it navigates to `/docs/<slug>/<path>/`) with a chevron, wrapped in `.nav-group`, with a `.nav-sub` containing the recursive include. Mark `current` when `node.path == current_path`.
- `node.type == 'document'` (no children) → plain link (unchanged).

Use the existing `.nav-group`/`.nav-sub` grid-collapse pattern so the JS open/close and CSS transition are reused.

### 6. CSS: `static/documentation/css/documentation.css`
After the sidebar nav block (~line 168), add a page-level open rule and keep current-link styling reusable:

```css
.nav-group.open > a.nav-page-link .chev{transform:rotate(90deg)}
.nav-page-link{display:flex;align-items:center;gap:.4rem}
.nav-page-link.current{background:var(--accent-soft);color:var(--fg);font-weight:500}
.nav-page-link.current::before{content:"";position:absolute;left:0;top:7px;bottom:7px;width:3px;border-radius:99px;background:var(--accent)}
```

### 7. JS: `static/documentation/js/navigation.js`
Extend the toggle selector so page-level links with children collapse like groups:

```js
document.querySelectorAll('.nav-group > button, .nav-group > a.nav-page-link').forEach(function(btn){
  btn.addEventListener('click', function(){ btn.parentElement.classList.toggle('open'); });
});
```
(The page link must stop default anchor navigation only when it is not the current page — or simpler: keep the chevron as a separate non-navigating element; implementation detail, note below.)

**Note on page-link click behavior:** clicking the label should navigate; clicking the chevron should toggle. Prefer wrapping the chevron in a `<button>` inside the anchor's row (or use a small `<span>` that calls `event.preventDefault()`). Recommend: render the page row as `<a>` (navigates) plus a `<button class="nav-page-toggle">` containing the chevron; add `.nav-page-toggle` to the JS selector list and `preventDefault()` in its handler.

## Validation (user-run — agent does not test)

1. Populate a `LocalDocumentationSource` pointing at a `docs/` folder arranged as:
   ```
   docs/introduction/0100-getting-started/quickstart.md
   docs/introduction/0100-getting-started/llm-ready-docs.md
   docs/introduction/0200-create-content/content-structure.md
   docs/introduction/0200-create-content/content-structure/space.md
   docs/introduction/0200-create-content/content-structure/collection.md
   docs/introduction/0200-create-content/formatting.md
   docs/developers/0100-api/overview.md
   ```
2. Open `/docs/<slug>/` — expect horizontal **tabs**: `Introduction`, `Developers`.
3. Click `Introduction` — sidebar shows groups `Get Started`, `Create Content`; group items show clean titles (numeric prefixes stripped): `Quickstart`, `LLM-ready docs`, `Content structure`, `Formatting`.
4. Expand `Content structure` (or navigate to `.../content-structure/`) — sub-pages `Sections`, `Groups` render; the active page is highlighted and its children auto-expanded.
5. Verify prev/next, breadcrumbs, and the drawer (mobile) mirror the same tree.
6. Confirm no broken internal links from markdown link rewriting (unchanged path format `/docs/<slug>/<path>/`).

## Risks / notes

- **Doc+folder collision** previously produced two same-path nodes; the merge pass now unifies them into one page-with-children node. Rebuild is on the shared `build_tree_from_paths` path so both Local and GitHub behave identically.
- **Numeric prefixes** change sort order and titles globally (including breadcrumbs / tabs / fallback titles via `title_from_name`). Unprefixed items sort last. Document this naming convention for content authors.
- **GitHub rate limits**: no new per-document reads introduced (ordering is filename-derived), keeping the existing tree caching (`docs:site:<id>:tree`) valid.
- Rebuilding the nav inverts the old assumption that a folder is "always just a container". Templates/JS/CSS must handle the third (page-with-children) case or it will render as a plain link with an orphaned sub-list.

## Out of scope

- Hidden/draft skipping in nav (needs per-doc reads).
- Frontmatter `order`/custom section labels.
- A `DocumentationSection` DB model.
- GitHub webhooks, versions, additional providers.
- Testing by the agent.
