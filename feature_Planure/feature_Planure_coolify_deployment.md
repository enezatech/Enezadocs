# Planure: Coolify-ready Docker Compose with auto-generated URL

## Feature Overview

Deploy the existing `docker-compose.yml` stack on [Coolify](https://coolify.io) with
zero manual host wiring: Coolify generates a public URL for the `web` service, and the
Django app automatically trusts that URL (allowed hosts + CSRF origins) without the
operator copying the domain into `DJANGO_ALLOWED_HOSTS`.

**Business objective:** one-click, proxy-fronted deployment on Coolify, while the same
`docker-compose.yml` keeps working for plain local `docker compose up`.

**Problem being solved**

- Today `web` only publishes `${WEB_PORT}:8000` on the host and reads
  `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` from `.env`. Behind Coolify's
  proxy the generated domain is unknown at build time, so the operator must manually
  paste it into the env or Django returns `400 DisallowedHost` / CSRF failures.
- The compose file has no `web` healthcheck, so Coolify cannot tell when the app is
  actually serving.
- Host port publishing bypasses Coolify's proxy and can conflict on the host.
- `POSTGRES_PASSWORD` is declared required, but `DATABASE_URL` defaults to the
  hardcoded `enezadocs:enezadocs` credential, so a Coolify operator who sets only
  `POSTGRES_PASSWORD` gets an auth failure.

**Expected user outcome / success criteria**

- Adding the repo as a **Docker Compose** resource in Coolify and setting
  `POSTGRES_PASSWORD` + `DJANGO_SECRET_KEY` is enough to get a working HTTPS URL.
- `SERVICE_URL_WEB_8000` triggers Coolify to generate and proxy a domain to container
  port `8000`; the app accepts that domain automatically.
- HTTPS termination at Coolify's proxy is honoured (no redirect loop, secure cookies
  work).
- Coolify shows the `web` service as healthy.
- `web` is not published on a public host port (proxy-only), while local
  `docker compose up` still exposes `http://localhost:${WEB_PORT}`.
- The stack still runs unchanged with a hand-written `.env` outside Coolify.
- No model or migration changes.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Domain trigger | Bare `SERVICE_URL_WEB_8000` entry in `web.environment` (Coolify magic variable). |
| URL discovery in the app | `settings.py` reads `DJANGO_PUBLIC_URL` first, then Coolify's `COOLIFY_URL` / `SERVICE_URL_WEB_8000` / `COOLIFY_FQDN` / `SERVICE_FQDN_WEB_8000`. |
| Host/origin parsing | `urllib.parse.urlsplit`; add `hostname` (port stripped) to `ALLOWED_HOSTS`, `scheme://hostname` to `CSRF_TRUSTED_ORIGINS`, de-duplicated. |
| DB URL | Keep `DATABASE_URL` authoritative; if unset, build it from `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_HOST`/`POSTGRES_PORT`/`POSTGRES_DB` (password URL-encoded). |
| TLS behind proxy | `DJANGO_SECURE_PROXY_SSL_HEADER=1` defaulted in compose (Coolify's proxy sets `X-Forwarded-Proto`). |
| Host port | Publish on loopback only: `127.0.0.1:${WEB_PORT:-8000}:8000` (proxy reaches the container over the Docker network). |
| Health check | HTTP `/healthz/` endpoint (no DB/auth) registered in `config/urls.py`; container `healthcheck` uses a TCP connect to avoid HTTPS-redirect interference. |
| `.env` loading | `env_file: .env` becomes optional (`required: false`) so Coolify's injected env is sufficient. |
| Testing | User-run only; the agent does not test. |

## Assumptions & transparency log

- **Assumption:** Coolify resolves `SERVICE_URL_WEB_8000` to a URL that may include a
  port and/or scheme; the settings helper strips the port and normalises scheme.
- **Assumption:** Coolify injects its predefined variables (`COOLIFY_URL`,
  `COOLIFY_FQDN`) and the magic `SERVICE_*` variables into the `web` container.
- **Assumption:** Coolify's proxy terminates TLS on standard ports, so `https://<host>`
  is the correct CSRF origin.
- **Trade-off:** `.hostname`-based CSRF origins drop a non-standard exposed port. This
  matches the standard Coolify proxy setup (80/443); documented as a limitation.
- **Trade-off:** the container healthcheck is a TCP probe rather than an HTTP probe, so
  it verifies the ASGI socket, not a full Django render; `/healthz/` remains available
  for Coolify's UI/HTTP health check over the public URL.
- The user is solely responsible for all testing and validation of the output.

## Components & modules involved

**Changed files**

- `config/views.py` *(new)* — `healthz` liveness view (`HttpResponse("ok")`, no DB).
- `config/urls.py` — register `path("healthz/", healthz, name="healthz")`.
- `config/settings.py` — add `_register_public_url()` helper; append generated hosts/
  origins after the existing `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` parsing; build
  `DATABASE_URL` from `POSTGRES_*` when it is empty.
- `docker-compose.yml` — add `SERVICE_URL_WEB_8000`; pass `POSTGRES_*` and
  `DATABASE_URL=${DATABASE_URL:-}` to `web`; default
  `DJANGO_SECURE_PROXY_SSL_HEADER=1`; add `web` healthcheck; loopback-bind the published
  port; mark `env_file` optional.
- `.env.sample` — document `DJANGO_PUBLIC_URL` and the Coolify auto-URL behaviour.
- `README.md` — add a short "Deploy on Coolify" subsection under the Docker option.
- `docs/Developer/changes/` — append an "As-built" note to the production Docker change
  doc (or a new dated doc) covering the Coolify variables and URL auto-trust.

**Unchanged**
- `Dockerfile`, `docker/entrypoint.sh`, all models, migrations, views/services, MCP,
  search, templates.
- `db` service definition (image, healthcheck, volume) beyond nothing.

## High-level Implementation Steps

Each step is atomic, independently actionable, and lists the user's success check.

### 1. Add the `/healthz/` liveness endpoint
Create `config/views.py` with a `healthz(request)` view returning a `200` plain
response and no database or auth access. Import and register it in `config/urls.py`.

**Success check:** `GET /healthz/` returns `200` with body `ok` (also when
`DJANGO_DEBUG=0`).

### 2. Auto-trust Coolify's generated public URL in `settings.py`
After the existing `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` assignment, add
`_register_public_url(url)`: normalise a missing scheme to `https://`, split with
`urlsplit`, append `hostname` to `ALLOWED_HOSTS` and `f"{scheme}://{hostname}"` to
`CSRF_TRUSTED_ORIGINS` (skip blanks and duplicates). Iterate, in order,
`DJANGO_PUBLIC_URL`, `COOLIFY_URL`, `SERVICE_URL_WEB_8000`, `COOLIFY_FQDN`,
`SERVICE_FQDN_WEB_8000`.

**Success check:** with `DJANGO_DEBUG=0` and
`SERVICE_URL_WEB_8000=https://app-abc.example.com:8000`, a shell prints
`app-abc.example.com` among `settings.ALLOWED_HOSTS` and
`https://app-abc.example.com` among `settings.CSRF_TRUSTED_ORIGINS`.

### 3. Derive `DATABASE_URL` from `POSTGRES_*` when absent
In the `not DEBUG and postgres` branch of `settings.py`, read `DATABASE_URL`; if empty,
build `postgres://<user>:<quoted password>@<host>:<port>/<db>` from
`POSTGRES_{USER,PASSWORD,HOST,PORT,DB}` (defaults `enezadocs`, ``, `db`, `5432`,
`enezadocs`) using `urllib.parse.quote`. Parse the result with `dj_database_url` as today.

**Success check:** with `DB_ENGINE=postgres`, `DJANGO_DEBUG=0`, `POSTGRES_PASSWORD=x`,
and no `DATABASE_URL`, the app connects to the `db` service on `5432` with user
`enezadocs`.

### 4. Compose: trigger Coolify URL generation
Add a bare `SERVICE_URL_WEB_8000` entry to `web.environment` so Coolify generates a
domain and routes it to container port `8000`. Keep the existing defaults for the rest.

**Success check:** after deploying, Coolify's resource shows a generated URL mapped to
the `web` service on port `8000`.

### 5. Compose: proxy/TLS and database env passthrough
Add to `web.environment`: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (same
defaults as `db`), `DATABASE_URL=${DATABASE_URL:-}`, and
`DJANGO_SECURE_PROXY_SSL_HEADER=${DJANGO_SECURE_PROXY_SSL_HEADER:-1}`.

**Success check:** over the Coolify HTTPS URL, login (session cookie) and admin POSTs
succeed with no CSRF error or redirect loop; the `web` container authenticates to
Postgres using `POSTGRES_PASSWORD`.

### 6. Compose: healthcheck, loopback port, optional `.env`
- Replace `ports: - "${WEB_PORT:-8000}:8000"` with
  `- "127.0.0.1:${WEB_PORT:-8000}:8000"` and add `expose: ["8000"]`.
- Add a `web.healthcheck` using
  `python -c "import socket; socket.create_connection(('127.0.0.1', 8000), 3).close()"`
  (interval `15s`, timeout `5s`, retries `5`, start_period `30s`).
- Change `env_file: .env` to the optional form
  `env_file: [{ path: .env, required: false }]`.

**Success check:** `docker compose ps` reports `web` as `healthy`; port `8000` is bound
to `127.0.0.1` only; `docker compose up` works with or without a `.env` file.

### 7. Documentation
Document `DJANGO_PUBLIC_URL` in `.env.sample`, add a "Deploy on Coolify" subsection to
`README.md` (required vars: `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`; the domain is
auto-generated and auto-trusted), and append an "As-built" note under
`docs/Developer/changes/`.

**Success check:** the README Coolify section and the change note describe the shipped
variable names and behaviour.

## Validation (user-run — the agent does not test)

1. `python manage.py check` — no errors, no migrations.
2. `docker compose config` — the file interpolates without errors.
3. Local: `docker compose up -d` (with `.env`) → `docker compose ps` shows `db` healthy
   and `web` healthy; `http://localhost:8000/healthz/` returns `ok`.
4. Local without `.env`: confirm compose still starts (env defaults apply).
5. Coolify: create a **Docker Compose** resource from the repo, set
   `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY`, deploy.
6. Confirm Coolify generates a URL for `web` on port `8000` and that the site loads over
   HTTPS.
7. Log in and submit an admin form over the generated HTTPS URL (CSRF + secure cookies).
8. Confirm the `web` container is reported healthy in Coolify.
9. Confirm `web` is not reachable on the server's public IP at port `8000`.

## Risks / notes

- **Variable availability:** if a Coolify version does not inject the magic/predefined
  variables, the app falls back to `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS`
  from the UI — set those manually in that case.
- **Port-in-origin:** CSRF origins use the hostname without port; a deployment that
  exposes a non-standard public port must add the full origin manually.
- **`SECURE_SSL_REDIRECT`:** keep it `1` only behind Coolify's HTTPS proxy (it sets
  `X-Forwarded-Proto`); plain-HTTP deployments must set it to `0`.
- **Compose version:** `env_file.required` needs Docker Compose v2.24+; older hosts
  should keep a real `.env`.
- **Healthcheck semantics:** the TCP probe proves the ASGI socket is open, not that
  Django can reach Postgres; the `db` healthcheck plus `depends_on` covers start order.
- **No schema impact:** the model field convention does not apply here.
- The user is solely responsible for all testing and validation of the output.

## Out of scope

- Coolify API/template metadata (`coolify.json`) or publishing to the Coolify template
  gallery.
- Traefik/Caddy labels or a raw-compose (manual proxy) deployment.
- Managed Postgres/Redis, queue workers, or horizontal scaling.
- Persisting Coolify-managed bind mounts beyond the existing named volumes.
- Changes to MCP, search, auth providers, or application behaviour.
- Agent-run testing.
