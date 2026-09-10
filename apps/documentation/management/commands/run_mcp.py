import importlib.util
import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Run the Django site and the MCP endpoint together on one ASGI server "
        "(uvicorn)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "addrport",
            nargs="?",
            default="127.0.0.1:8000",
            help="Optional host:port to bind (default 127.0.0.1:8000).",
        )
        parser.add_argument(
            "--no-reload",
            action="store_true",
            help="Disable auto-reload on code changes.",
        )

    def handle(self, *args, **options):
        try:
            import uvicorn
        except ImportError:
            raise CommandError(
                "uvicorn is required to run the MCP server. "
                "Install it with: pip install -r requirements.txt",
            )

        host, port = self._parse_addrport(options["addrport"])
        reload = not options["no_reload"]
        if reload and importlib.util.find_spec("watchfiles") is None:
            self.stderr.write(
                "watchfiles is not installed; auto-reload is disabled. "
                "Install uvicorn[standard] to enable it.",
            )
            reload = False

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        self.stdout.write(
            f"Serving Django + MCP on http://{host}:{port} "
            f"(MCP endpoint at the configured MCP_PATH).",
        )
        uvicorn.run(
            "config.asgi:application",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )

    def _parse_addrport(self, addrport):
        addrport = (addrport or "").strip()
        if not addrport:
            return "127.0.0.1", 8000
        if ":" in addrport:
            host, _, port = addrport.rpartition(":")
        else:
            host, port = "127.0.0.1", addrport
        host = host or "127.0.0.1"
        try:
            port = int(port)
        except ValueError:
            raise CommandError(f"Invalid port: {port!r}")
        return host, port
