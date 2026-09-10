from __future__ import annotations

from django.utils.text import slugify as django_slugify

from .base import NavigationNode


def title_from_name(name: str) -> str:
    stem = name[:-3] if name.endswith(".md") else name
    return stem.replace("-", " ").replace("_", " ").strip().title()


def slugify_path(path: str) -> str:
    """Return ``path`` with every non-leaf segment slugified.

    Section and group folder segments become lowercase kebab-case; the final
    document segment keeps its authored name.
    """
    path = (path or "").strip("/")
    if not path:
        return ""
    parts = path.split("/")
    head = [django_slugify(part) or part for part in parts[:-1]]
    return "/".join(head + [parts[-1]])


def build_tree_from_paths(paths: list[str]) -> list[NavigationNode]:
    root = NavigationNode(title="", path="", type="folder")
    for path in sorted(paths):
        parts = [part for part in path.split("/") if part]
        if not parts:
            continue
        _insert(root, parts)
    return root.children


def _insert(root: NavigationNode, parts: list[str]) -> None:
    current = root
    folder_parts: list[str] = []
    for part in parts[:-1]:
        folder_parts.append(part)
        folder_path = "/".join(folder_parts)
        child = next(
            (c for c in current.children if c.type == "folder" and c.path == folder_path),
            None,
        )
        if child is None:
            child = NavigationNode(
                title=title_from_name(part),
                path=folder_path,
                type="folder",
                key=folder_path,
            )
            current.children.append(child)
        current = child
    current.children.append(
        NavigationNode(
            title=title_from_name(parts[-1]),
            path="/".join(parts),
            type="document",
            key="/".join(parts),
        ),
    )


def docs_first(nodes: list[NavigationNode]) -> list[NavigationNode]:
    """Return children ordered so documents precede subfolders (stable)."""
    for node in nodes:
        if node.children:
            node.children = docs_first(node.children)
    documents = [node for node in nodes if node.type != "folder"]
    folders = [node for node in nodes if node.type == "folder"]
    return documents + folders


def flatten(nodes: list[NavigationNode]) -> list[NavigationNode]:
    result: list[NavigationNode] = []
    for node in nodes:
        if node.type == "document":
            result.append(node)
        result.extend(flatten(node.children))
    return result


def find_node(nodes: list[NavigationNode], path: str) -> NavigationNode | None:
    for node in nodes:
        if node.type == "document" and node.path == path:
            return node
        if node.type == "folder":
            found = find_node(node.children, path)
            if found is not None:
                return found
    return None


def first_document(node: NavigationNode) -> str | None:
    for child in node.children:
        if child.type == "document":
            return child.path
        found = first_document(child)
        if found is not None:
            return found
    return None


def first_page(node: NavigationNode) -> str | None:
    if node.type == "document" and node.path:
        return node.path
    return first_document(node)


def contains_path(node: NavigationNode, path: str) -> bool:
    if node.type == "document" and node.path == path:
        return True
    return any(contains_path(child, path) for child in node.children)


def _node_key(node: NavigationNode) -> str:
    return node.key or node.path or node.uid


def collect_open_keys(nodes: list[NavigationNode], current_path: str) -> set[str]:
    keys: set[str] = set()
    for node in nodes:
        if node.children and contains_path(node, current_path):
            keys.add(_node_key(node))
        keys |= collect_open_keys(node.children, current_path)
    return keys
