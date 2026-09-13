# Enezadocs

A self-hosted documentation platform that renders Markdown from **local folders** and
**GitHub repositories** through one unified, themeable UI. Markdown stays the source of
truth; the database only stores configuration, sync state, and search indexes.

This application lets you add documentation as you go, right alongside your repository,
so you can keep docs up to date on the fly. It also includes an MCP server that allows
your coding agent to read your documentation directly.

---

## Features

- **Unified sources** — serve documentation from the local filesystem or a GitHub
  repository (public or private via token) behind the same interface.
- **Markdown-first rendering** — server-side rendering with frontmatter, callouts,
  syntax highlighting, heading anchors, table of contents, and prev/next navigation.
- **Hybrid search** — tokenized BM25 (SQLite FTS5, with pure-Python fallback) fused with
  local `fastembed` embeddings via Reciprocal Rank Fusion. No content leaves the server.
- **MCP server** — read-only [Model Context Protocol](https://modelcontextprotocol.io)
  endpoints so AI agents can discover and read scoped documentation over Streamable HTTP.
- **Scoped access** — each MCP server is bound to a site, section, or group and
  authenticated with its own bearer tokens.
- **Authentication** — email sign-up/login plus optional GitHub and Google SSO
  (django-allauth).
- **Multi-site home page** — featured sites, quick paths, and release updates managed
  from the Django admin.
- **Offline-friendly** — responses are cached, so previously fetched documents remain
  available when GitHub is unreachable.
- **Production-ready deployment** — Docker image with PostgreSQL, WhiteNoise static
  serving, and a full environment-variable configuration surface.

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend | Django 6.1, Python 3.13 |
| ASGI server | Uvicorn (`config.asgi:application`) |
| Database | SQLite (development) / PostgreSQL 16 (production) |
| Markdown | `markdown`, `python-frontmatter`, `Pygments`, `nh3` |
| Search | SQLite FTS5 / BM25 + `fastembed` embeddings |
| Auth | `django-allauth` (email + GitHub/Google SSO) |
| Static files | WhiteNoise |
| Object storage (optional) | Any S3-compatible endpoint (`boto3`) |

## Project layout

```
Enezadocs/
├── manage.py
├── config/                     # Django project (settings, urls, asgi/wsgi)
├── apps/
│   └── documentation/          # The documentation app
│       ├── models.py           # Sites, sources, MCP servers/tokens, search index
│       ├── views.py            # Site index, document, search, asset proxy, home
│       ├── urls.py
│       ├── admin.py
│       ├── services/           # Providers, markdown, navigation, search, MCP
│       ├── management/commands # sync_docs, build_docs_index, run_mcp, ...
│       ├── templates/documentation/
│       └── static/documentation/
├── docs/                       # Markdown content served by the app
├── templates/                  # allauth template overrides
├── Dockerfile
├── docker-compose.yml
├── docker/entrypoint.sh
├── requirements.txt
└── .env.sample
```

## Requirements

- Python 3.13+
- pip
- Docker + Docker Compose (for the containerized deployment)
- A PostgreSQL 16 server (only for the production/Docker path)

---

## Installation

### Option A — Local development (SQLite)

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd Enezadocs
   ```

2. **Create and activate a virtual environment**

   ```bash
   # Windows (PowerShell)
   python -m venv env
   .\env\Scripts\Activate.ps1

   # macOS / Linux
   python -m venv env
   source env/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the environment (optional for local dev)**

   The app runs with sane development defaults (SQLite, `DEBUG=1`, allowed hosts `*`).
   To override them, copy the sample and edit it:

   ```bash
   cp .env.sample .env
   ```

   For local development, set `DB_ENGINE=sqlite`. Load the file into your shell
   (`export $(grep -v '^#' .env | xargs)` on Linux, or use a tool such as
   `python-dotenv`). The app reads configuration from environment variables only.

5. **Apply migrations**

   ```bash
   python manage.py migrate
   ```

6. **Create an admin account**

   ```bash
   python manage.py createsuperuser
   ```

7. **Run the server**

   ```bash
   python manage.py runserver
   ```

   Open `http://127.0.0.1:8000/`. The admin is at `http://127.0.0.1:8000/admin/`.

8. **Add a documentation site**

   In the admin, create a `DocumentationSource` (LOCAL pointing at a folder, or GITHUB
   pointing at an `owner/repository`) and a `DocumentationSite` that uses it. Then open
   `http://127.0.0.1:8000/docs/<slug>/`.

   For a LOCAL source you can also add pages from the admin: open the site and use
   **Upload markdown** to write `.md` files into the source root or an existing
   section/group folder (filesystem or S3-backed). Navigation and search refresh
   automatically after each upload.

### Option B — Docker (Production, PostgreSQL)

1. **Create the environment file**

   ```bash
   cp .env.sample .env
   ```

   Edit `.env` and at minimum set:

   - `DJANGO_SECRET_KEY` — generate with
     `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
     This key also encrypts stored GitHub/MCP tokens; keep it stable.
   - `POSTGRES_PASSWORD` — a strong password.
   - `DJANGO_ALLOWED_HOSTS` — your real host(s), not `*`.
   - `DJANGO_CSRF_TRUSTED_ORIGINS` — e.g. `https://docs.example.com`.

   `DB_ENGINE=postgres` and a matching `DATABASE_URL` are already set in the sample.

2. **Build and start the stack**

   ```bash
   docker compose build
   docker compose up -d
   ```

   This starts two services:

   - `db` — PostgreSQL 16 with a persistent `pgdata` volume.
   - `web` — the Django site and MCP endpoints on port `8000` (override with `WEB_PORT`).

   On start the entrypoint runs `migrate`, `collectstatic`, then serves the app with
   Uvicorn.

3. **Create an admin account**

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

4. **Open the app**

   Visit `http://localhost:8000/` (or your configured host) and the admin at
   `/admin/`.

5. **Persistent data**

   Named volumes keep state across restarts and updates: `pgdata` (database),
   `media_data` (uploaded media), `static_data` (collected static files), `docs_data`
   (documentation content), and `fastembed_cache` (embedding model cache).

   Updating the app (`docker compose build` then `docker compose up -d`) reuses these
   volumes and never resets them. They are removed **only** by destructive commands:

   - `docker compose down -v` (or `--volumes`)
   - `docker volume rm enezadocs_pgdata` (and the other named volumes)
   - `docker volume prune` / `docker system prune --volumes`

   Never run those against a production stack. On Coolify, keep the option that removes
   volumes on redeploy disabled.

   Non-regenerable content lives in `pgdata`, `media_data`, and `docs_data`; back it up
   before any destructive operation. `static_data` (repopulated by `collectstatic`) and
   `fastembed_cache` (re-downloaded on demand) are regenerable.

   `POSTGRES_PASSWORD` is captured when the `pgdata` volume is first created and must
   stay stable. Changing it later does not update the role inside the database, so the app
   stops connecting even though the data is intact; to change it, run
   `ALTER USER <user> WITH PASSWORD '<new>'` inside the `db` container.

   > **Note:** `docs_data` is populated from the image's `docs/` folder only when the
   > volume is first created. Updating the image does not refresh documentation already
   > stored in the volume — run `sync_docs` / re-import, or use a bind mount, if the
   > bundled `docs/` must track the image.

> **Reverse proxy / HTTPS:** the compose file does not include a TLS terminator. Put
> Nginx, Caddy, or a cloud load balancer in front of `web` in production and enable the
> `DJANGO_SECURE_*` flags in `.env` once HTTPS is in place.

---

## Configuration

All settings are read from environment variables; `.env.sample` documents every option.
Key groups:

| Group | Variables |
| --- | --- |
| Core | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` |
| Database | `DB_ENGINE`, `DATABASE_URL`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| Security | `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SESSION_COOKIE_SECURE`, `DJANGO_CSRF_COOKIE_SECURE`, `DJANGO_SECURE_HSTS_*`, `DJANGO_X_FRAME_OPTIONS` |
| Paths / storage | `DJANGO_STATIC_ROOT`, `DJANGO_MEDIA_ROOT`, `FASTEMBED_CACHE_PATH` |
| Auth / SSO | `GITHUB_CLIENT_ID`, `GITHUB_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_SECRET`, `GITHUB_TOKEN` |
| MCP | `MCP_ENABLED`, `MCP_PATH`, `MCP_MAX_CONTENT_CHARS` |
| Search | `DOCS_SEMANTIC_*`, `DOCS_CACHE_*` |
| S3 (optional) | `DOCS_S3_ENABLED`, `DOCS_S3_BUCKET`, `DOCS_S3_PREFIX`, `DOCS_S3_REGION`, `DOCS_S3_ENDPOINT_URL`, `DOCS_S3_ACCESS_KEY_ID`, `DOCS_S3_SECRET_ACCESS_KEY`, `DOCS_S3_USE_PATH_STYLE` (`DOCS_S3_ENABLED`: 1 force S3, 0 force local, blank = S3 when the bucket is set) |

---

## Management commands

```bash
python manage.py sync_docs           # pull latest content for enabled GitHub sources
python manage.py import_structure    # (re)import the navigation tree
python manage.py build_docs_index    # build the search / semantic index
python manage.py validate_docs       # report broken links, missing assets, bad frontmatter
python manage.py run_mcp             # serve the site + MCP endpoints (uvicorn wrapper)
python manage.py create_mcp_token --name "Docs agent" --server developer
python manage.py setup_social_apps   # configure allauth social providers
```

Run `build_docs_index` after changing documentation content so search stays current.

## MCP endpoints

Each `MCPServer` row exposes a read-only endpoint at:

```
<MCP_PATH>/<server-slug>/        # e.g. http://localhost:8000/mcp/developer/
```

Requests authenticate with `Authorization: Bearer <token>`. See
`docs/Developer/mcp-documentation-server.md` for scoping, tokens, and the tool list
(`get_scope`, `get_navigation`, `search_docs`, `get_document`, `get_document_section`, ...).

---

## Development notes

- Local virtual environments live in `env/` and are git-ignored.
- Runtime artifacts (`db.sqlite3`, `media/`, `staticfiles/`, `.env`) are git-ignored.
- Documentation content under `docs/` is tracked and served by the app.
- Model field conventions: one field per line, a `verbose_name` on every field, and
  multi-line field declarations close `)` on its own aligned line.
