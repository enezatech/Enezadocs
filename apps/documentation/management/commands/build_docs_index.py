from django.core.management.base import BaseCommand

from documentation.models import DocumentationSite
from documentation.services.documentation import DocumentationService
from documentation.services.search import build_index


class Command(BaseCommand):
    help = "Rebuild the documentation search index."

    def add_arguments(self, parser):
        parser.add_argument("--slug", nargs="*", default=[])

    def handle(self, *args, **options):
        sites = DocumentationSite.objects.filter(enabled=True)
        if options["slug"]:
            sites = sites.filter(slug__in=options["slug"])
        for site in sites:
            service = DocumentationService(site)
            build_index(service)
            self.stdout.write(f"Indexed {site.slug}")
        self.stdout.write(self.style.SUCCESS("Search index rebuilt."))
