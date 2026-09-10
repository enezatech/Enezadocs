import os

from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_app = get_asgi_application()

if settings.DEBUG:
    # Under an ASGI server there is no StaticFilesHandler, so admin/static
    # assets would 404. Serve them in development.
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

    django_app = ASGIStaticFilesHandler(django_app)

if getattr(settings, "MCP_ENABLED", False):
    from documentation.mcp_server.server import build_asgi_app

    application = build_asgi_app(django_app)
else:
    application = django_app
