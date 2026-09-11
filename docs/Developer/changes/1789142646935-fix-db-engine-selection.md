# Change: Fix DB_ENGINE=postgres being silently ignored

**Date:** 2026-09-11

## Goal

Make `DB_ENGINE=postgres` actually select PostgreSQL, regardless of `DEBUG`. Previously the
Postgres branch was gated on `not DEBUG`, so with `DEBUG` true (the default, and the state
inside the Docker container) the app fell back to SQLite even though `DB_ENGINE=postgres`
and `DATABASE_URL` were set.

## What changed

| Area | Change |
| --- | --- |
| Database selection | `config/settings.py` now chooses the backend from `DB_ENGINE` alone (`if DB_ENGINE in ("postgres", "postgresql")`); the `not DEBUG and` condition was removed. |
| Error message | With `DB_ENGINE=postgres` and no `DATABASE_URL`, startup raises a clear `ImproperlyConfigured` instead of a bare `KeyError`. |
| Compose env loading | `docker-compose.yml` `web` now declares an optional `env_file: .env` (`required: false`), so the whole `.env` (DEBUG, SECRET_KEY, SSO, MCP, search tuning, ...) reaches the container. Explicit `environment` entries still take precedence, and Coolify can still deploy with no `.env` file. |
| Compose DEBUG | `web.environment` sets `DJANGO_DEBUG: ${DJANGO_DEBUG:-0}`, so the container's `DEBUG` reflects `.env` and defaults off in Docker. |

## Notes

- The SQLite fallback is still the default only when `DB_ENGINE` is unset or set to
  `sqlite`, so local development without a `.env` is unchanged.
- This corrects the earlier production-Docker plan's locked decision, which specified
  `DB_ENGINE` as the sole selector (no `DEBUG` coupling).
- `env_file.required` needs Docker Compose v2.24+; older hosts must keep a real `.env`
  or rely on Coolify-injected variables.
- No model, migration, or schema changes.

## User validation

1. With `DB_ENGINE=postgres` and `DATABASE_URL` set:
   `python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"`
   prints `django.db.backends.postgresql`.
2. Same command with `DJANGO_DEBUG=1` still prints the Postgres backend.
3. With `DB_ENGINE=postgres` and no `DATABASE_URL`, startup raises the clear
   `ImproperlyConfigured` message.
4. With `DB_ENGINE` unset, the backend is `django.db.backends.sqlite3`.
5. Set `DJANGO_DEBUG=1` in `.env`, run `docker compose config` (shows `DJANGO_DEBUG: "1"`),
   then `docker compose exec web python manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"`
   prints `True`; set it to `0` and confirm `False`.
