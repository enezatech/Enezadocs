from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = "Provision GitHub and Google SocialApp records from settings."

    def handle(self, *args, **options):
        site = Site.objects.get_current()
        for provider, cfg in settings.SOCIALACCOUNT_PROVIDERS.items():
            app_cfg = cfg.get("APP", {})
            client_id = app_cfg.get("client_id", "")
            secret = app_cfg.get("secret", "")
            if not client_id or not secret:
                self.stdout.write(
                    self.style.WARNING(f"{provider}: credentials missing, skipping")
                )
                continue
            app, created = SocialApp.objects.get_or_create(
                provider=provider,
                defaults={
                    "name": provider.title(),
                    "client_id": client_id,
                    "secret": secret,
                },
            )
            if not created:
                app.client_id = client_id
                app.secret = secret
                app.save()
            app.sites.add(site)
            self.stdout.write(
                self.style.SUCCESS(f"{provider}: {'created' if created else 'updated'}")
            )
