---
menu name: Production Docker + PostgreSQL
position: 6
---

# Planure: Production Docker + PostgreSQL + Security Environment

> **Note:** the project convention is `feature_Planure/feature_Planure_production_docker_postgres.md`,
> but that path is blocked by workspace edit permissions. This plan was saved to the
> allowed plan location. Copy it into `feature_Planure/` if desired.

## Feature Overview

Prepare **Enezadocs** (Django 6.1 / Python 3.13) for production deployment as a
single container plus a PostgreSQL database, with all secrets and deployment
settings moved into environment variables documented by a sample env file.

**Problem being solved:** the app is dev-only today — SQLite is hard-coded
(`config/settings.py:63-68`), `DEBUG` defaults on, `ALLOWED_HOSTS` defaults to
`*`, there is no Dockerfile/docker-compose, no env sample, and no root
`.gitignore`.

**Expected user outcome / success criteria:**
- `docker compose up` starts a `web` service (Django site **and** the MCP
  endpoint) and a `db` service (PostgreSQL 16) with persistent named volumes.
- `DB_ENGINE` in the env file selects SQLite or PostgreSQL; PostgreSQL is read
  from a single `DATABASE_URL`.
- Every security-relevant Django setting (secret key, debug, allowed hosts,
  CSRF origins, cookie/HSTS/HTTPS flags) is read from env and documented in
  `.env.sample`.
- Root `.gitignore` ignores runtime junk while `docs/` content stays tracked.
- No secret is baked into the image or committed to git.

## Locked decisions

| Decision | Choice |
| --- | --- |
| DB selection | `DB_ENGINE` env, `sqlite` (default) or `postgres`; explicit `if` in `settings.py`. **Both DBs supported.** |
| PostgreSQL URL | Single `DATABASE_URL` read from env (parsed with `dj-database-url`) |
| PG driver | `psycopg[binary]` (psycopg 3; Django 6.1 recommended) |
| Web server | `uvicorn config.asgi:application` (keeps `/mcp` ASGI endpoint working) |
| Static files | WhiteNoise + `collectstatic` at container start; `STATIC_ROOT` |
| Reverse proxy / MinIO | **Out of scope** — compose is `web` + `db` only |
| Persistence | Named volumes: postgres data, media, docs content, staticfiles, FastEmbed cache |
| `.gitignore` / `docs` | Track `docs/` markdown normally; ignore runtime junk |
| `DEBUG` default | Keep code default `1` for local dev; compose/env sets `DJANGO_DEBUG=0` |

## Environment variables (final set)

**New — core / URLs**
- `DJANGO_SECRET_KEY` *(exists)*
- `DJANGO_DEBUG` *(exists)*
- `DJANGO_ALLOWED_HOSTS` *(exists; compose should set explicit host, not `*`)*
- `DJANGO_CSRF_TRUSTED_ORIGINS` *(new; comma-separated scheme://host)*

**New — database**
- `DB_ENGINE` = `sqlite` | `postgres`
- `DATABASE_URL` = `postgres://user:pass@db:5432/enezadocs`
- `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` *(consumed by the `db` service)*

**New — security**
- `DJANGO_SECURE_SSL_REDIRECT` (bool)
- `DJANGO_SESSION_COOKIE_SECURE` (bool)
- `DJANGO_CSRF_COOKIE_SECURE` (bool)
- `DJANGO_SECURE_HSTS_SECONDS` (int)
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` (bool)
- `DJANGO_SECURE_HSTS_PRELOAD` (bool)
- `DJANGO_SECURE_PROXY_SSL_HEADER` (bool → `SECURE_PROXY_SSL_HEADER`)
- `DJANGO_X_FRAME_OPTIONS` (default `DENY`)
- `DJANGO_SECURE_CONTENT_TYPE_NOSNIFF` (bool, default on)

**New — paths / storage**
- `DJANGO_STATIC_ROOT` (default `BASE_DIR/staticfiles`)
- `DJANGO_MEDIA_ROOT` (default `BASE_DIR/media`)
- `FASTEMBED_CACHE_PATH` (default `/cache/fastembed`) — persistent model cache

**Existing (document in `.env.sample`, unchanged behavior)**
- `GITHUB_CLIENT_ID`, `GITHUB_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_SECRET`
- `GITHUB_TOKEN`
- `DOCS_CACHE_TREE_TTL`, `DOCS_CACHE_DOCUMENT_TTL`, `DOCS_CACHE_ASSET_TTL`
- `MCP_ENABLED`, `MCP_PATH`, `MCP_MAX_CONTENT_CHARS`
- `DOCS_S3_BUCKET`, `DOCS_S3_PREFIX`, `DOCS_S3_REGION`, `DOCS_S3_ENDPOINT_URL`,
  `DOCS_S3_ACCESS_KEY_ID`, `DOCS_S3_SECRET_ACCESS_KEY`, `DOCS_S3_USE_PATH_STYLE`
- `DOCS_SEMANTIC_SEARCH_ENABLED`, `DOCS_SEMANTIC_LEXICAL_BACKEND`,
  `DOCS_SEMANTIC_EMBEDDINGS_BACKEND`, `DOCS_SEMANTIC_EMBEDDINGS_MODEL`,
  `DOCS_SEMANTIC_CHUNK_CHARS`, `DOCS_SEMANTIC_CHUNK_OVERLAP`,
  `DOCS_SEMANTIC_RRF_K`, `DOCS_SEMANTIC_TOP_K`

## Components & modules involved

**Changed files**
- `config/settings.py` — DB if-statement, security env wiring, `STATIC_ROOT`,
  WhiteNoise middleware, media root from env.
- `requirements.txt` — add `psycopg[binary]`, `dj-database-url`, `whitenoise`.

**New files**
- `Dockerfile`
- `.dockerignore`
- `docker-compose.yml`
- `.env.sample`
- `.gitignore` (repo root)
- `docker/entrypoint.sh`

**Unchanged:** models, migrations, services, views, templates, MCP server, admin.

## Ordered tasks

### 1. Add dependencies — `requirements.txt`
Append (keep existing lines):
```
psycopg[binary]>=3.2
dj-database-url>=2.2
whitenoise>=6.7
```

### 2. Database selection — `config/settings.py`
Replace the hard-coded `DATABASES` block (lines 63-68) with an explicit
if-statement. Prefer `import dj_database_url` at the top.

Non-executable guidance:
```python
DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").strip().lower()
if DB_ENGINE in ("postgres", "postgresql"):
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
```
Success: `DB_ENGINE=sqlite` keeps the current behavior; `DB_ENGINE=postgres`
with `DATABASE_URL` set produces a Postgres `default` entry.

### 3. Security settings from env — `config/settings.py`
Add after `ALLOWED_HOSTS` (line 15):
```python
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]
```
Add near the end of the file a block reading every `DJANGO_SECURE_*` /
cookie / X-Frame env var listed above, using small `_env_bool` / `_env_int`
helpers defined at module level. Defaults must preserve current local-dev
behavior (all secure flags off unless the env enables them).
Success: with an empty `.env`, the app starts exactly as before.

### 4. Static + media — `config/settings.py`
- Add `STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))`.
- Add `MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))`.
- Keep `STATIC_URL`/`MEDIA_URL`.
- Insert `"whitenoise.middleware.WhiteNoiseMiddleware"` immediately after
  `"django.middleware.security.SecurityMiddleware"` (line 34).
- Add a `STORAGES` block using
  `whitenoise.storage.CompressedManifestStaticFilesStorage` for `staticfiles`.
Success: `collectstatic` populates `STATIC_ROOT`; the site can serve static
assets without a separate web server.

### 5. Dockerfile — `Dockerfile`
- Base `python:3.13-slim`.
- `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`.
- `apt-get install -y --no-install-recommends libgomp1` (required by
  onnxruntime/fastembed) and clean apt lists.
- Create a non-root `app` user; set workdir `/app`.
- Copy `requirements.txt` first, `pip install --no-cache-dir -r requirements.txt`.
- Copy the project, `chown` to `app`.
- `EXPOSE 8000`; `ENTRYPOINT ["/app/docker/entrypoint.sh"]`.
Success: `docker build` completes and the image contains the app + deps.

### 6. Entrypoint — `docker/entrypoint.sh`
Runs, in order, then starts the server:
1. `python manage.py migrate --noinput`
2. `python manage.py collectstatic --noinput`
3. `exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-3}"`
Must be executable (LF line endings). Do not create a superuser here.
Success: container boots migrated, static collected, ASGI serving.

### 7. docker-compose — `docker-compose.yml`
- `web`: `build: .`, `env_file: .env`, `ports: ["8000:8000"]`,
  `depends_on: db` (condition `service_healthy`), `restart: unless-stopped`,
  volumes: `media_data:/app/media`, `static_data:/app/staticfiles`,
  `docs_data:/app/docs`, `fastembed_cache:/cache`.
- `db`: `image: postgres:16-alpine`, env `POSTGRES_DB/USER/PASSWORD` from
  env, `volume: pgdata:/var/lib/postgresql/data`, `healthcheck`
  (`pg_isready -U $POSTGRES_USER`), `restart: unless-stopped`.
- Top-level `volumes:` — `pgdata`, `media_data`, `static_data`, `docs_data`,
  `fastembed_cache`.
- Set `FASTEMBED_CACHE_PATH=/cache/fastembed` for `web`.
Success: `docker compose config` validates; `up` starts both services with
persistent storage. `docs_data` is seeded from the image's `docs/` on first
create (Docker copies image content into an empty named volume).

### 8. `.env.sample` — repo root
Document every variable from the list above with safe placeholder values and
short comments (which are required, which default). Include both a SQLite and
a PostgreSQL example for `DB_ENGINE`/`DATABASE_URL`. Never put real secrets.
Success: copying it to `.env` and filling values is sufficient to run compose.

### 9. Root `.gitignore`
Ignore: `.env`, `.env.*` (but **not** `.env.sample`), `env/`, `.venv/`,
`__pycache__/`, `*.py[cod]`, `db.sqlite3`, `media/`, `staticfiles/`,
`.kilo/agent-manager.json`, `*.log`, OS/editor junk (`.DS_Store`, `Thumbs.db`,
`.idea/`, `.vscode/`). **Do not ignore `docs/`.**
Success: `git status` shows `docs/` content as trackable and no runtime junk.

### 10. `.dockerignore`
Exclude `env/`, `.git/`, `__pycache__/`, `*.pyc`, `db.sqlite3`, `media/`,
`staticfiles/`, `docs_data` artifacts, `.env*`, `.kilo/`, `test/`, `plans`.
Success: build context is small and leaks no secrets.

## Risks / notes

- **FTS5 is SQLite-only.** `services/search.py:179-192` creates an FTS5 table;
  under PostgreSQL it fails silently and lexical scoring falls back to the
  in-Python BM25 path (`search.py:142-176`). Search still works, just slower —
  acceptable for v1; adding PostgreSQL full-text search is out of scope.
- **`SECRET_KEY` is the encryption key** for `EncryptedTextField`
  (`services/crypto.py:10-13`). Rotating it makes existing stored GitHub
  tokens/MCP tokens undecryptable — set it once and keep it stable.
- **FastEmbed first run needs network.** The model downloads into
  `FASTEMBED_CACHE_PATH`; the `fastembed_cache` volume must persist across
  restarts to avoid re-downloading.
- **WhiteNoise serves static only, not uploaded media** (`MEDIA_ROOT` logos).
  Serving `/media/` is out of scope here; add nginx or object storage later if
  needed.
- **SQLite + multiple workers** is unsafe for writes; compose defaults to
  PostgreSQL. Keep `DB_ENGINE=sqlite` for local dev only.
- **Non-root user** must be able to write `media/`, `staticfiles/`, `docs/`,
  and `/cache`; named volumes must be writable by the `app` user.

## Validation (user-run — the agent does not test)

1. `docker compose config` — valid, env substituted.
2. Copy `.env.sample` → `.env`, set `DB_ENGINE=postgres` and a strong
   `DJANGO_SECRET_KEY` / `POSTGRES_PASSWORD`; `docker compose build`.
3. `docker compose up -d`; `docker compose ps` shows `db` healthy and `web` up.
4. `docker compose exec web python manage.py check` — no errors.
5. `docker compose exec web python manage.py createsuperuser`; open
   `http://localhost:8000/admin/`.
6. Confirm Postgres is used: `docker compose exec db psql -U <user> -d <db> -c "\dt"`
   lists Django tables.
7. Confirm MCP endpoint responds at the configured `MCP_PATH`
   (`http://localhost:8000/mcp/testfun/`) and admin static assets load.
8. Restart the stack (`docker compose down && up -d`) — DB rows, media, docs,
   and the FastEmbed cache persist.
9. Switch `DB_ENGINE=sqlite` and re-run — app starts on SQLite (dev fallback).
10. `git status` — `docs/` content tracked, `.env` and runtime junk ignored.

## Out of scope

- Nginx/reverse proxy, TLS certificates, MinIO/S3 service.
- PostgreSQL full-text search backend for `services/search.py`.
- CI/CD, image registry publishing, Celery/queues.
- Changing model fields, migrations, or application logic.
- Agent-run testing (the user is solely responsible for testing and validation).
