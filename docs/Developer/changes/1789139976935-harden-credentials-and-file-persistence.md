# Change: Harden credentials and guarantee file persistence across updates

**Date:** 2026-09-11

## Goal

Ensure an app update (rebuild / redeploy / `docker compose up -d`) cannot lose or detach
persistent data, and cannot silently break the credentials the app uses to reach it.

## What changed

| Area | Change |
| --- | --- |
| Postgres password | `docker-compose.yml` now uses a single required `POSTGRES_PASSWORD` for both the `db` service and the `web` `DATABASE_URL`, replacing Coolify's auto-generated `SERVICE_PASSWORD_*` Postgres magic variable. Missing value fails fast at `docker compose config`/`up`. |
| Database docs | `.env.sample` and `README.md` state that `POSTGRES_PASSWORD` is captured at first initialization of the `pgdata` volume and must stay stable; changing it later requires `ALTER USER ... WITH PASSWORD ...` inside the DB. |
| File volumes | `README.md` documents that the named volumes (`pgdata`, `media_data`, `static_data`, `docs_data`, `fastembed_cache`) survive updates and are removed only by `down -v`, `docker volume rm`, or `docker volume prune`; notes which are non-regenerable and the Coolify redeploy toggle to keep off. |
| `docs_data` seeding | `README.md` notes the volume is seeded from the image's `docs/` only when first created, so image updates do not refresh already-seeded content (use `sync_docs`/re-import or a bind mount). |
| S3 credentials | `config/settings.py` raises `ImproperlyConfigured` when `DOCS_S3_BUCKET` is set but exactly one of `DOCS_S3_ACCESS_KEY_ID` / `DOCS_S3_SECRET_ACCESS_KEY` is set. Both blank or both set remain valid. `.env.sample` documents the rule. |

## Notes

- Persistence itself was already correct (`pgdata` named volume, pinned compose project
  name); this change hardens credentials and documents the operational safeguards.
- The `S3` guard preserves boto3's default credential chain (e.g. an IAM role) for
  deployments that leave both credential variables blank.
- No model, migration, or schema changes; the repo model-field convention is unaffected.

## User validation

1. `docker compose config` with `POSTGRES_PASSWORD` set — `db` and `web` show the same
   password.
2. Unset `POSTGRES_PASSWORD` — `docker compose config` errors with the fail-fast message.
3. `docker compose up -d` on the existing stack — `web` connects to `db`; existing rows
   are intact.
4. `docker compose exec db psql -U <user> -d <db> -c "\dt"` lists Django tables.
5. `docker compose restart web` (without `-v`) — files under `/app/docs` and uploaded
   media remain present.
6. With `DOCS_S3_BUCKET` set and only `DOCS_S3_ACCESS_KEY_ID` set, Django startup raises
   `ImproperlyConfigured`; with both or neither set, startup is unchanged.
