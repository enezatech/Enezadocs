---
menu name: Local Node Folder Lifecycle
position: 5
---

# Planure: Local Node Folder Lifecycle (create on section/group, lock root, delete with content)

## Feature Overview

For documentation sources of type **LOCAL**, the Django admin should keep the
`DocumentationNode` section/group rows and the real filesystem folders in sync:

- Creating a **section or group** node creates its folder under the local source root.
- The local source **root folder** (`LocalDocumentationSource.root_path`) cannot be changed once set.
- Deleting a node deletes **its folder and everything inside it**.

Problem: today `DocumentationNodeAdmin.save_model` only writes a DB row; authors must
create folders by hand, deletes leave orphaned folders/content, and `root_path` can be
repointed at any time, silently orphaning all node paths.

Success criteria:
- Add a section/group on a LOCAL-source site → folder appears at `<root_path>/<node.path>`.
- The `root_path` field is not editable on an existing `LocalDocumentationSource`.
- Delete a section/group → its folder (and any markdown/subfolders in it) is removed.
- GitHub sources and non-node models are unaffected.
- `rebuild_from_provider_tree` / sync never create or delete folders.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Hook location | **Django admin only** (`DocumentationNodeAdmin`). No model signals. |
| "Main folder" | `LocalDocumentationSource.root_path` — locked after the local source exists. |
| Create trigger | Add of a `section`/`group` node whose `site.source.source_type == LOCAL`, with non-empty `path`. |
| Create behavior | `mkdir(parents=True, exist_ok=True)` at `<root>/<path>`. Root must already exist. |
| Delete behavior | `shutil.rmtree(<root>/<path>)` — recursive, **content included**. |
| Never touch | The root folder itself (refuse when `path` is empty or resolves to root). |
| Failure handling | Block the DB operation: create errors surface as form errors before save; delete errors abort before the DB row is removed. |
| GitHub sources | No filesystem operations. |
| Schema | No model/migration changes. |

## Components & modules involved

**Changed files**
- `apps/documentation/admin.py`
  - `LocalDocumentationSourceForm` (NEW) — disable `root_path` when the instance exists.
  - `LocalDocumentationSourceInline` — use the form.
  - `DocumentationNodeAdminForm` (NEW) — `clean()` validates + creates the folder on add.
  - `DocumentationNodeAdmin` — `form = DocumentationNodeAdminForm`; override
    `delete_model` / `delete_queryset` to delete folders before removing rows.
  - Module-level private helpers: `_local_root(site)`, `_resolve_target(root, path)`,
    `_is_local_node(node)`, `_create_node_folder(node)`, `_delete_node_folder(node)`.

> Note: the project rules prefer `feature_Planure/feature_Planure_local_node_folder_lifecycle.md`.
> That path is blocked by workspace edit permissions, so this plan was saved to the
> allowed plan location. Copy it there if desired.

**Unchanged**
- `models.py`, `services/*` (providers, `structure.py`, `sync.py`), `views.py`,
  templates, `DocumentationSearchDocument`, search index.

## Ordered tasks

### 1. Local root lock — `admin.py`
Add a form that renders `root_path` read-only once the inline row exists:

```python
class LocalDocumentationSourceForm(forms.ModelForm):
    class Meta:
        model = LocalDocumentationSource
        fields = ("root_path",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["root_path"].disabled = True
```

Set `form = LocalDocumentationSourceForm` on `LocalDocumentationSourceInline`.
(Disabled fields keep the stored value; the field stays editable on the add form.)

### 2. Path helpers — `admin.py` (module level)
Mirror the provider's safety rules (`services/filesystem.py:14-21`):

```python
def _local_root(site):
    try:
        config = site.source.local
    except LocalDocumentationSource.DoesNotExist:
        raise ValidationError("Local source has no root path configured.")
    return Path(config.root_path).expanduser().resolve()

def _resolve_target(root, path):
    clean = (path or "").strip("/\\")
    if not clean:
        raise ValidationError({"path": "A folder path is required."})
    target = (root / clean).resolve()
    if target == root or root not in target.parents:
        raise ValidationError({"path": "Path escapes the documentation root."})
    return target
```

- `_is_local_node(node)` → `node.type in ("section", "group")` and
  `node.site.source.source_type == DocumentationSource.SourceType.LOCAL`.
- `_create_node_folder(node)`: root must `is_dir()` (else `ValidationError`);
  `target.mkdir(parents=True, exist_ok=True)`.
- `_delete_node_folder(node)`: skip unless `_is_local_node`; reject empty path /
  `target == root`; if another `DocumentationNode` for the same source resolves to the
  same folder, skip and warn (shared-source guard); else `shutil.rmtree(target)` when
  `target.is_dir()`, or `target.unlink()` when it is a file; ignore missing.
- Imports needed: `Path`, `shutil`, `LocalDocumentationSource.DoesNotExist`,
  `ValidationError`.

### 3. Create folder on add — `admin.py`
```python
class DocumentationNodeAdminForm(forms.ModelForm):
    class Meta:
        model = DocumentationNode
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk is None and cleaned.get("site") is not None:
            probe = DocumentationNode(
                site=cleaned["site"],
                type=cleaned.get("type"),
                path=cleaned.get("path") or "",
            )
            if _is_local_node(probe):
                try:
                    _create_node_folder(probe)
                except ValidationError:
                    raise
                except OSError as exc:
                    raise ValidationError({"path": f"Could not create folder: {exc}"})
        return cleaned
```
Set `form = DocumentationNodeAdminForm` on `DocumentationNodeAdmin`.
`clean()` runs last, so a failure blocks the save and shows the error on `path`.

### 4. Delete folder with content — `admin.py`
```python
def delete_model(self, request, obj):
    _delete_node_folder(obj)          # raises OSError → atomic delete rolls back
    super().delete_model(request, obj)

def delete_queryset(self, request, queryset):
    for obj in queryset:
        _delete_node_folder(obj)      # deletes all folders first
    super().delete_queryset(request, queryset)
```
`delete_view` runs inside `transaction.atomic` (Django `options.py:2508`), so a
filesystem error prevents the DB delete. `rebuild_from_provider_tree` calls
`queryset.delete()` directly and never goes through the admin, so structure imports
remain non-destructive.

### 5. Verify no collateral changes
Confirm `import_structure` (`admin.py:34`), `sync_source`, and the admin sync action
still work unchanged (they do not call `delete_model`/`save_model`).

## Validation (user-run — the agent does not test)

1. `python manage.py check` (no schema change, no migration needed).
2. Admin → Documentation Sources → create a source with `source_type=LOCAL` and a
   `root_path` pointing at the repo's `docs/`. Save.
3. Reopen it → `root_path` is shown read-only and cannot be changed.
4. Admin → Documentation Nodes → add a `section` for that source's site with
   `path=Developer/New Section`. Save → `docs/Developer/New Section/` exists.
5. Add a `group` with `path=Developer/New Section/Guides` → nested folder is created.
6. Put a markdown file inside the section folder → it renders as a page.
7. Delete the section node → confirmation page appears; on confirm, the folder and the
   markdown file inside are gone.
8. Create a node on a GITHUB-source site → no filesystem changes (admin still saves).
9. Re-run `Import navigation structure` → nodes are rebuilt and **no folders are deleted**.
10. Attempt an empty path on add → form error, node not saved.
11. Attempt `path=../outside` → form error, nothing created.

## Risks / notes

- **Shared local source**: two sites can point at the same `root_path`; the delete guard
  skips filesystem removal when another node resolves to the same folder (removes only
  that node's DB row). Review the warning message.
- **Pre-existing folders are reused**: `exist_ok=True` means an add never fails because
  the folder already exists; no ownership is tracked, so deleting a node can remove
  content another author created there.
- **Partial delete on bulk action**: `delete_queryset` removes folders first; a failure
  midway leaves earlier folders gone while rows remain. Accepted v1.
- **No cleanup on DB failure after creation**: folder creation happens in `clean()`;
  if the DB insert later fails, the empty folder remains.
- **Root must pre-exist**: a missing `root_path` is an error, never auto-created
  (protects the "main folder").
- Only the admin path is guarded; shell/script edits to nodes or `root_path` bypass this.

## Out of scope

- Model signals / global hooks; sync or GitHub folder operations.
- Creating starter `index.md` files, moving/renaming folders when `path` changes.
- Rebuilding nodes from the filesystem in the other direction.
- A friendly custom delete error page (failure currently aborts with an admin error).
- Agent-run testing.
