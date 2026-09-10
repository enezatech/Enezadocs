from django.core.management.base import BaseCommand

from documentation.services.sync import sync_all


class Command(BaseCommand):
    help = "Synchronize documentation sources from GitHub."

    def handle(self, *args, **options):
        sync_all()
        self.stdout.write(self.style.SUCCESS("Documentation synchronized."))
