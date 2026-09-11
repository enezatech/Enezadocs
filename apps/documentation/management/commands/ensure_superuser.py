import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser from environment variables if it does not exist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=os.environ.get("DJANGO_SUPERUSER_USERNAME", ""),
            help="Superuser username.",
        )
        parser.add_argument(
            "--email",
            default=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
            help="Superuser email address.",
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("DJANGO_SUPERUSER_PASSWORD", ""),
            help="Superuser password.",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "Superuser bootstrap skipped: set DJANGO_SUPERUSER_USERNAME "
                    "and DJANGO_SUPERUSER_PASSWORD to enable it.",
                ),
            )
            return

        user_model = get_user_model()

        if user_model.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Superuser '{username}' already exists; skipping.",
                ),
            )
            return

        user_model.objects.create_superuser(
            username=username,
            email=options["email"].strip(),
            password=password,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Created superuser '{username}'."),
        )
