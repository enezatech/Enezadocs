import posixpath
import re

from django.core.management.base import BaseCommand

from documentation.models import DocumentationSite
from documentation.services.documentation import DocumentationService
from documentation.services.navigation import flatten
from documentation.services.search import parse_frontmatter


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def resolve_target(base_dir, target):
    target = target.split("#", 1)[0]
    if target.endswith(".md"):
        target = target[:-3]
    if target.startswith("/"):
        return posixpath.normpath(target).lstrip("/")
    return posixpath.normpath(posixpath.join(base_dir, target)).lstrip("/")


class Command(BaseCommand):
    help = "Validate documentation sources."

    def handle(self, *args, **options):
        for site in DocumentationSite.objects.filter(enabled=True):
            service = DocumentationService(site)
            flat = flatten(service.tree())
            paths = {node.path for node in flat}
            broken = []
            for node in flat:
                raw = service.get_raw(node.path)
                if raw is None:
                    continue
                _, body = parse_frontmatter(raw)
                base_dir = posixpath.dirname(node.path)
                for target in LINK_RE.findall(body):
                    if target.startswith(("http://", "https://", "mailto:", "#")):
                        continue
                    if resolve_target(base_dir, target) not in paths:
                        broken.append((node.path, target))
            self.stdout.write(
                f"{site.slug}: {len(flat)} files, {len(broken)} broken links"
            )
            for doc, target in broken:
                self.stdout.write(self.style.WARNING(f"  {doc} -> {target}"))
        self.stdout.write(self.style.SUCCESS("Validation complete."))
