import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "apps"))


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


def _env_hosts(name: str) -> list[str]:
    """Parse a comma-separated host list, dropping any ':port' suffix.

    Django matches ALLOWED_HOSTS against the host without the port, so an
    entry like 'docs.example.com:8000' would never match.
    """
    hosts = []
    for value in os.environ.get(name, "").split(","):
        value = value.strip()
        if not value:
            continue
        host, _, port = value.rpartition(":")
        hosts.append(host if host and port.isdigit() else value)
    return hosts


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-enezadocs-dev-only-change-me",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = _env_hosts("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    # Coolify injects COOLIFY_FQDN into the container at runtime; it follows the
    # resource's domain configuration. _env_hosts drops any ':port' suffix.
    ALLOWED_HOSTS = _env_hosts("COOLIFY_FQDN")
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = [
    origin
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin
]
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        origin
        for origin in os.environ.get("COOLIFY_URL", "").split(",")
        if origin
    ]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.google",
    "documentation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "documentation.context_processors.site_branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").strip().lower()

if not DEBUG and DB_ENGINE in ("postgres", "postgresql"):
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            os.environ["DATABASE_URL"],
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
STATIC_ROOT = _env_path("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles")
MEDIA_ROOT = _env_path("DJANGO_MEDIA_ROOT", BASE_DIR / "media")

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "optional"
SOCIALACCOUNT_LOGIN_ON_GET = True

SOCIALACCOUNT_PROVIDERS = {
    "github": {
        "APP": {
            "client_id": os.environ.get("GITHUB_CLIENT_ID", ""),
            "secret": os.environ.get("GITHUB_SECRET", ""),
        },
        "SCOPE": ["read:user", "user:email"],
    },
    "google": {
        "APP": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_SECRET", ""),
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "enezadocs-docs-cache",
    }
}

DOCS_CACHE_TREE_TTL = int(os.environ.get("DOCS_CACHE_TREE_TTL", "300"))
DOCS_CACHE_DOCUMENT_TTL = int(os.environ.get("DOCS_CACHE_DOCUMENT_TTL", "300"))
DOCS_CACHE_ASSET_TTL = int(os.environ.get("DOCS_CACHE_ASSET_TTL", "900"))

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

MCP_ENABLED = os.environ.get("MCP_ENABLED", "1") == "1"
MCP_PATH = os.environ.get("MCP_PATH", "/mcp")
MCP_MAX_CONTENT_CHARS = int(os.environ.get("MCP_MAX_CONTENT_CHARS", "40000"))

DOCS_S3 = {
    "BUCKET": os.environ.get("DOCS_S3_BUCKET", "").strip(),
    "PREFIX": os.environ.get("DOCS_S3_PREFIX", "").strip().strip("/"),
    "REGION": os.environ.get("DOCS_S3_REGION", "").strip(),
    "ENDPOINT_URL": os.environ.get("DOCS_S3_ENDPOINT_URL", "").strip(),
    "ACCESS_KEY_ID": os.environ.get("DOCS_S3_ACCESS_KEY_ID", "").strip(),
    "SECRET_ACCESS_KEY": os.environ.get("DOCS_S3_SECRET_ACCESS_KEY", "").strip(),
    "USE_PATH_STYLE": os.environ.get("DOCS_S3_USE_PATH_STYLE", "0") == "1",
}
DOCS_S3["ENABLED"] = bool(DOCS_S3["BUCKET"])

if DOCS_S3["ENABLED"]:
    _s3_has_key = bool(DOCS_S3["ACCESS_KEY_ID"])
    _s3_has_secret = bool(DOCS_S3["SECRET_ACCESS_KEY"])
    if _s3_has_key != _s3_has_secret:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "DOCS_S3_ACCESS_KEY_ID and DOCS_S3_SECRET_ACCESS_KEY must be set together "
            "when DOCS_S3_BUCKET is configured (set both, or leave both blank to use "
            "the default credential chain).",
        )

DOCS_SEMANTIC_SEARCH = {
    "ENABLED": os.environ.get("DOCS_SEMANTIC_SEARCH_ENABLED", "1") == "1",
    "LEXICAL_BACKEND": os.environ.get("DOCS_SEMANTIC_LEXICAL_BACKEND", "fts5"),
    "EMBEDDINGS_BACKEND": os.environ.get("DOCS_SEMANTIC_EMBEDDINGS_BACKEND", "fastembed"),
    "EMBEDDINGS_MODEL": os.environ.get(
        "DOCS_SEMANTIC_EMBEDDINGS_MODEL",
        "BAAI/bge-small-en-v1.5",
    ),
    "CHUNK_CHARS": int(os.environ.get("DOCS_SEMANTIC_CHUNK_CHARS", "1000")),
    "CHUNK_OVERLAP": int(os.environ.get("DOCS_SEMANTIC_CHUNK_OVERLAP", "200")),
    "RRF_K": int(os.environ.get("DOCS_SEMANTIC_RRF_K", "60")),
    "TOP_K": int(os.environ.get("DOCS_SEMANTIC_TOP_K", "20")),
}

SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_CSRF_COOKIE_SECURE", False)
SECURE_HSTS_SECONDS = _env_int("DJANGO_SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    False,
)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
X_FRAME_OPTIONS = os.environ.get("DJANGO_X_FRAME_OPTIONS", "DENY")
SECURE_CONTENT_TYPE_NOSNIFF = _env_bool("DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", True)

if _env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
