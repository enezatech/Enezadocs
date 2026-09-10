from collections import Counter
from urllib.parse import quote

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .models import (
    DocumentationNode,
    DocumentationSearchDocument,
    DocumentationSite,
    HomePage,
)
from .services.documentation import DocumentationService
from .services.navigation import (
    collect_open_keys,
    contains_path,
    first_document,
    first_page,
    flatten,
    slugify_path,
)


def _get_site(slug):
    return get_object_or_404(DocumentationSite, slug=slug, enabled=True)


class HomeView(View):
    def get(self, request):
        home = HomePage.load()
        sites = list(DocumentationSite.objects.filter(enabled=True))
        authenticated = request.user.is_authenticated

        categories = self._categories(sites)
        guide_counts = self._guide_counts(sites)
        section_qs = DocumentationNode.objects.filter(
            site__enabled=True,
            enabled=True,
            type=DocumentationNode.NodeType.SECTION,
        )
        group_qs = DocumentationNode.objects.filter(
            site__enabled=True,
            enabled=True,
            type=DocumentationNode.NodeType.GROUP,
        )
        section_counts = Counter(section_qs.values_list("site_id", flat=True))
        group_counts = Counter(group_qs.values_list("site_id", flat=True))
        for site in sites:
            site.guide_count = guide_counts.get(site.source_id, 0)
            site.section_count = section_counts.get(site.id, 0)
            site.group_count = group_counts.get(site.id, 0)
        featured = self._featured(home, authenticated)

        context = {
            "home": home,
            "sites": sites,
            "categories": categories,
            "featured": featured,
            "quick_paths": home.quick_paths.all(),
            "quick_install_bullets": [
                bullet.strip()
                for bullet in home.quick_install_bullets.splitlines()
                if bullet.strip()
            ],
            "updates": home.updates.all(),
            "stat_sites": len(sites),
            "stat_articles": sum(guide_counts.values()),
            "stat_sections": sum(section_counts.values()),
            "stat_groups": sum(group_counts.values()),
            "stat_latest": home.latest_release,
        }
        return render(request, "documentation/home.html", context)

    def _categories(self, sites):
        counts = Counter()
        for site in sites:
            cat = (site.category or "").strip()
            if cat:
                counts[cat] += 1
        return [{"name": name, "count": count} for name, count in counts.items()]

    def _guide_counts(self, sites):
        counts = Counter()
        source_ids = [site.source_id for site in sites]
        if source_ids:
            counts.update(
                DocumentationSearchDocument.objects.filter(
                    source_id__in=source_ids,
                ).values_list("source_id", flat=True)
            )
        return counts

    def _featured(self, home, authenticated):
        featured = []
        for fs in home.featured_sites.all():
            site = fs.site
            featured.append(
                {
                    "title": fs.title or site.name,
                    "subtitle": fs.subtitle or site.description,
                    "slug": site.slug,
                    "icon": site.icon,
                    "docs": self._featured_docs(site, authenticated),
                }
            )
        return featured

    def _featured_docs(self, site, authenticated):
        try:
            service = DocumentationService(site, authenticated=authenticated)
            tree = service.tree()
        except Exception:
            return []
        docs = [node for node in flatten(tree) if node.type == "document"][:4]
        return [{"title": node.title, "path": node.path} for node in docs]


class SearchAllView(View):
    def get(self, request):
        query = (request.GET.get("q", "") or "").strip()
        if not query:
            return JsonResponse({"results": []})
        authenticated = request.user.is_authenticated
        results = []
        needle = query.lower()
        for site in DocumentationSite.objects.filter(enabled=True):
            hay = f"{site.name} {site.description or ''} {site.category or ''}".lower()
            if needle in hay:
                results.append(
                    {
                        "type": "site",
                        "title": site.name,
                        "sub": site.category or site.name,
                        "excerpt": site.description or "",
                        "href": f"/docs/{site.slug}/",
                    }
                )
            try:
                service = DocumentationService(site, authenticated=authenticated)
                for item in service.search(query):
                    results.append(
                        {
                            "type": "article",
                            "title": item["title"],
                            "sub": site.name,
                            "excerpt": item["description"],
                            "url_path": slugify_path(item["path"]),
                            "href": f"/docs/{site.slug}/{slugify_path(item['path'])}/",
                        }
                    )
            except Exception:
                continue
        return JsonResponse({"results": results[:20]})


class SiteIndexView(View):
    def get(self, request):
        return redirect("home")


class DocumentationView(View):
    def get(self, request, slug, path=""):
        site = _get_site(slug)
        authenticated = request.user.is_authenticated
        service = DocumentationService(site, authenticated=authenticated)
        path = service.resolve_url_path(path)
        path = self._resolve_path(service, path)
        if not authenticated and self._is_private(service, path):
            return self._redirect_to_login(request)
        document = service.document(path)
        context = self._context(site, service, path)
        if document is None:
            return render(request, "documentation/404.html", context, status=404)
        context["document"] = document
        return render(request, "documentation/document.html", context)

    def _resolve_path(self, service, path):
        path = (path or "").strip("/")
        if path:
            return path
        flat = service.flat_paths()
        if "index" in flat:
            return "index"
        return flat[0] if flat else ""

    def _is_private(self, service, path):
        """True when an anonymous visitor may not see the resolved path.

        Content counts as private when it exists in the full navigation tree
        but is absent from the anonymous (public) tree — either because an
        ancestor section/group is private or the page declares private access.
        A missing path keeps its existing 404 behavior.
        """
        full_paths = set(service.full_flat_paths())
        if not full_paths:
            return False
        if path:
            if path not in full_paths:
                return False
            return path not in set(service.flat_paths())
        return not service.flat_paths()

    def _redirect_to_login(self, request):
        next_url = quote(request.get_full_path())
        return redirect(f"{reverse('account_login')}?next={next_url}")

    def _context(self, site, service, path):
        tree = service.tree()
        if service.structure_mode:
            tabs, active_tab, nav_tree = self._structure_navigation(
                site,
                tree,
                path,
            )
        else:
            tabs, active_tab, nav_tree = self._folder_navigation(
                site,
                tree,
                path,
            )
        return {
            "site": site,
            "tabs": tabs,
            "active_tab": active_tab,
            "nav_tree": nav_tree,
            "current_path": path,
            "open_keys": collect_open_keys(tree, path),
            "search_url": f"/docs/{site.slug}/search/",
            "github_url": service.source_home_url(),
        }

    def _structure_navigation(self, site, tree, path):
        tabs = []
        for node in tree:
            landing = first_page(node)
            tabs.append(
                {
                    "key": node.key or node.uid,
                    "title": node.title,
                    "url": (
                        f"/docs/{site.slug}/{slugify_path(landing)}/"
                        if landing
                        else ""
                    ),
                },
            )
        active = next(
            (node for node in tree if contains_path(node, path)),
            None,
        )
        if active is None:
            active = tree[0] if tree else None
        active_tab = active.key or active.uid if active is not None else ""
        nav_tree = active.children if active is not None else []
        return tabs, active_tab, nav_tree

    def _folder_navigation(self, site, tree, path):
        loose = [node for node in tree if node.type != "folder"]
        folders = [node for node in tree if node.type == "folder"]
        tabs = []
        for doc in loose:
            tabs.append(
                {
                    "key": doc.path,
                    "title": self._tab_title(doc.path, doc.title),
                    "path": doc.path,
                    "url": f"/docs/{site.slug}/{slugify_path(doc.path)}/",
                },
            )
        for folder in folders:
            landing = first_document(folder)
            tabs.append(
                {
                    "key": folder.path,
                    "title": folder.title,
                    "path": folder.path,
                    "url": (
                        f"/docs/{site.slug}/{slugify_path(landing)}/"
                        if landing
                        else f"/docs/{site.slug}/{slugify_path(folder.path)}/"
                    ),
                },
            )
        active_tab = path.split("/")[0] if "/" in path else (path or "")
        active_folder = next(
            (folder for folder in folders if folder.path == active_tab),
            None,
        )
        if active_folder is not None:
            nav_tree = active_folder.children
        else:
            nav_tree = loose
        return tabs, active_tab, nav_tree

    def _tab_title(self, path, fallback):
        if path in ("index", "home", "readme"):
            return "Home"
        return fallback


class SearchView(View):
    def get(self, request, slug):
        site = _get_site(slug)
        service = DocumentationService(site, authenticated=request.user.is_authenticated)
        query = request.GET.get("q", "")
        results = service.search(query)
        for item in results:
            item["url_path"] = slugify_path(item["path"])
        return JsonResponse({"results": results})


class AssetProxyView(View):
    def get(self, request, slug, path):
        site = _get_site(slug)
        service = DocumentationService(site)
        asset = service.get_asset(path)
        if asset is None:
            return HttpResponse(status=404)
        data, content_type = asset
        response = HttpResponse(data, content_type=content_type)
        response["Cache-Control"] = "public, max-age=86400"
        return response
