from django.core.management.base import BaseCommand, CommandError

from documentation.models import DocumentationSite
from documentation.services.factory import get_provider
from documentation.services.structure import rebuild_from_provider_tree


class Command(BaseCommand):
    help = "Replace a site's DB navigation structure with nodes imported from its provider layout."

    def add_arguments(self, parser):
        parser.add_argument("--site", required=True, help="DocumentationSite slug.")

    def handle(self, *args, **options):
        slug = options["site"]
        try:
            site = DocumentationSite.objects.get(slug=slug)
        except DocumentationSite.DoesNotExist:
            raise CommandError(f"No DocumentationSite with slug {slug!r}.")

        provider = get_provider(site.source)
        count = rebuild_from_provider_tree(site, provider.get_tree())
        self.stdout.write(
            self.style.SUCCESS(f"Imported {count} navigation nodes for site {slug!r}."),
        )
