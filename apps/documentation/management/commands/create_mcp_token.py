from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from documentation.models import (
    DocumentationNode,
    DocumentationSite,
    MCPServer,
    MCPToken,
)
from documentation.services.mcp_tokens import generate_token, hash_token


class Command(BaseCommand):
    help = "Create a scoped MCP server (if needed) and issue a token for it."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Token name.")
        parser.add_argument(
            "--server",
            required=True,
            help="MCP server slug. Created if it does not exist.",
        )
        parser.add_argument(
            "--server-name",
            default="",
            help="Display name when creating a new server.",
        )
        parser.add_argument("--site", default="", help="Site slug.")
        parser.add_argument("--section", default="", help="Section id or title.")
        parser.add_argument("--group", default="", help="Group id or title.")
        parser.add_argument("--allow-private", action="store_true")

    def handle(self, *args, **options):
        slug = slugify(options["server"])
        server = (
            MCPServer.objects.select_related("site", "section", "group")
            .filter(slug=slug)
            .first()
        )
        created = False
        if server is None:
            server = self._create_server(slug, options)
            created = True

        raw, prefix = generate_token()
        token = MCPToken(
            name=options["name"],
            prefix=prefix,
            token_hash=hash_token(raw),
            token=raw,
            server=server,
            allow_private=options["allow_private"],
        )
        token.full_clean()
        token.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created MCP server '{server.name}' at <base>/{server.slug}/.",
                ),
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Created MCP token '{token.name}' for server '{server.slug}'.",
            ),
        )
        self.stdout.write(raw)

    def _create_server(self, slug, options):
        if not options["site"]:
            raise CommandError(
                f"MCP server '{slug}' does not exist; pass --site to create it.",
            )
        try:
            site = DocumentationSite.objects.get(slug=options["site"])
        except DocumentationSite.DoesNotExist:
            raise CommandError(f"Unknown site slug: {options['site']}")

        section = self._resolve(
            site,
            options["section"],
            DocumentationNode.NodeType.SECTION,
            "section",
        )
        group = self._resolve(
            site,
            options["group"],
            DocumentationNode.NodeType.GROUP,
            "group",
        )
        server = MCPServer(
            name=options["server_name"] or options["server"],
            slug=slug,
            site=site,
            section=section,
            group=group,
        )
        server.full_clean()
        server.save()
        return server

    def _resolve(self, site, value, node_type, label):
        value = (value or "").strip()
        if not value:
            return None
        queryset = DocumentationNode.objects.filter(site=site, type=node_type)
        node = None
        if value.isdigit():
            node = queryset.filter(pk=int(value)).first()
        if node is None:
            node = queryset.filter(title=value).first()
        if node is None:
            raise CommandError(
                f"No {label} matching '{value}' on site '{site.slug}'.",
            )
        return node
