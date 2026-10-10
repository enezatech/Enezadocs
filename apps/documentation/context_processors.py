from django.conf import settings
from django.core.cache import cache

from .models import HomePage
from .services.documentation import HOME_PAGE_CACHE_KEY


def site_branding(request):
    home = cache.get(HOME_PAGE_CACHE_KEY) if not settings.DEBUG else None
    if home is None:
        home = HomePage.load()
        if not settings.DEBUG:
            cache.set(HOME_PAGE_CACHE_KEY, home, settings.DOCS_CACHE_HOME_TTL)
    return {"home": home}
