from django.core.management.base import BaseCommand

from documentation.models import DocumentationSite
from documentation.services.documentation import DocumentationService
from documentation.services.search import build_index
from documentation.services.sync import invalidate_source


class Command(BaseCommand):
    help = "Rebuild the documentation search index."

    def add_arguments(self, parser):
        parser.add_argument("--slug", nargs="*", default=[])

    def handle(self, *args, **options):
        sites = DocumentationSite.objects.filter(enabled=True)
        if options["slug"]:
            sites = sites.filter(slug__in=options["slug"])
        sources = {}
        for site in sites:
            service = DocumentationService(site)
            build_index(service)
            sources[site.source_id] = site.source
            self.stdout.write(f"Indexed {site.slug}")
        for source in sources.values():
            invalidate_source(source)
        self.stdout.write(self.style.SUCCESS("Search index rebuilt."))
