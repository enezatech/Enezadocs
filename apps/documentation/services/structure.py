from __future__ import annotations

import posixpath

import frontmatter

from .access import PRIVATE, raw_access
from .base import NavigationNode
from .navigation import flatten, title_from_name

NODE_TYPE_SECTION = "section"
NODE_TYPE_GROUP = "group"

MENU_KEYS = ("menu name", "menu_name", "menu", "menu-name")


def _page_meta(raw: str | None) -> dict:
    try:
        post = frontmatter.loads(raw or "")
        return dict(post.metadata or {})
    except Exception:
        return {}


def _page_label_and_order(raw: str | None, fallback: str) -> tuple[str, int | None]:
    meta = _page_meta(raw)
    menu = None
    for key in MENU_KEYS:
        value = meta.get(key)
        if value is not None:
            menu = value
            break
    if menu is not None:
        label = str(menu).strip() or fallback
    else:
        title = str(meta.get("title") or "").strip()
        label = title or fallback
    position = meta.get("position")
    order = None
    if position is not None:
        try:
            order = int(float(str(position).replace(",", "").strip()))
        except (TypeError, ValueError):
            order = None
    return label, order


def build_structure_tree(site, provider_tree, read_raw, authenticated=True) -> list[NavigationNode]:
    """Assemble the navigation tree from section/group nodes plus auto pages.

    Every enabled markdown file found directly inside a node's folder becomes a
    page. Page label and ordering come from the file's frontmatter (menu name /
    position); position is only considered within the same group.

    ``authenticated=False`` filters the tree for anonymous visitors: a node
    whose access (or an ancestor's access) is private is skipped together with
    its whole subtree, and pages whose own frontmatter declares private access
    are skipped.
    """
    from documentation.models import DocumentationNode

    rows = list(
        DocumentationNode.objects.filter(
            site=site,
            enabled=True,
            type__in=[NODE_TYPE_SECTION, NODE_TYPE_GROUP],
        ),
    )
    if not rows:
        return []

    children_of: dict[int | None, list] = {}
    for row in rows:
        children_of.setdefault(row.parent_id, []).append(row)

    provider_docs = [n for n in flatten(provider_tree) if n.type == "document"]
    docs_by_dir: dict[str, list[NavigationNode]] = {}
    for doc in provider_docs:
        docs_by_dir.setdefault(posixpath.dirname(doc.path), []).append(doc)

    def pages_for(folder: str) -> list[NavigationNode]:
        found = docs_by_dir.get(folder or "", [])
        pages: list[NavigationNode] = []
        for doc in found:
            path = doc.path
            raw = None
            try:
                raw = read_raw(path)
            except Exception:
                raw = None
            if not authenticated and raw is not None and raw_access(raw) == PRIVATE:
                continue
            label, order = _page_label_and_order(raw, doc.title or title_from_name(path))
            pages.append(
                NavigationNode(
                    title=label,
                    path=path,
                    type="document",
                    order=order,
                    key=path,
                ),
            )
        pages.sort(
            key=lambda n: (
                n.order if n.order is not None else 10**9,
                n.title.lower(),
                n.path,
            ),
        )
        return pages

    def convert(rows_to_convert: list, inherited_private: bool = False) -> list[NavigationNode]:
        out: list[NavigationNode] = []
        for row in sorted(rows_to_convert, key=lambda r: (r.order, r.pk)):
            private = inherited_private or row.access == PRIVATE
            if private and not authenticated:
                continue
            folder = (row.path or "").strip("/")
            node = NavigationNode(
                title=row.title,
                type="folder",
                order=row.order,
                key=str(row.pk),
            )
            node.children = convert(children_of.get(row.pk, []), private) + pages_for(folder)
            if not authenticated and not node.children:
                continue
            out.append(node)
        return out

    return convert(children_of.get(None, []))


def rebuild_from_provider_tree(site, tree) -> int:
    """Rebuild a site's section/group rows from a provider folder tree.

    Top-level provider folders become sections; any deeper folder becomes a
    group. Markdown files are intentionally not stored — they become pages
    automatically during rendering.
    """
    from documentation.models import DocumentationNode

    DocumentationNode.objects.filter(site=site).delete()
    counter = 0

    def add(parent, nodes: list[NavigationNode]) -> None:
        nonlocal counter
        order = 0
        for node in nodes:
            if node.type != "folder":
                continue
            kind = NODE_TYPE_SECTION if parent is None else NODE_TYPE_GROUP
            row = DocumentationNode(
                site=site,
                parent=parent,
                type=kind,
                title=node.title,
                path=(node.path or "").strip("/"),
                order=order,
            )
            row.save()
            counter += 1
            if node.children:
                add(row, node.children)
            order += 1

    add(None, tree)
    return counter
