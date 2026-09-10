from django.conf import settings
from django.core.cache import cache


def fetch_asset(provider, source, path):
    key = f"docs:source:{source.id}:asset:{path}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = provider.get_asset(path)
    if result is None:
        return None
    cache.set(key, result, settings.DOCS_CACHE_ASSET_TTL)
    return result
