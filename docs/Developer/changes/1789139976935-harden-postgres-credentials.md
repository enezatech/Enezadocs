# Plan: Harden credentials and guarantee file persistence across updates

## Goal

Ensure an app update (rebuild / redeploy / `docker compose up -d`) can **never** lose or
detach persistent data, and can **never** silently break the credentials the app uses to
reach that data:

1. **PostgreSQL** — one explicit, fail-fast password variable shared by `db` and `web`.
2. **File-storage volumes** — verify + document that `docs_data`, `media_data`,
   `static_data`, and `fastembed_cache` survive updates.
3. **S3 document-storage credentials** — fail fast on a partial credential set instead of
   silently falling back to boto3's default chain.

## Findings (verified in repo)

**Postgres**
- `docker-compose.yml:10` — `db` uses `POSTGRES_PASSWORD: ${SERVICE_PASSWORD_POSTGRES}`
  (opaque Coolify magic var, not operator-settable).
- `docker-compose.yml:41` — `web` builds `DATABASE_URL` from
  `${SERVICE_PASSWORD_POSTGRES}` with no default.
- `.env.sample:33` and `README.md:167` tell operators to set `POSTGRES_PASSWORD`, but
  compose currently ignores it.
- `config/settings.py:128` hard-requires `DATABASE_URL` (no fallback), so a mismatch is a
  hard crash that looks like a lost DB.
- Postgres applies `POSTGRES_PASSWORD` only at **initdb**; changing it later leaves the
  stored role password unchanged.
- Persistence is already correct: named volume `pgdata` (`docker-compose.yml:12`),
  project name pinned (`docker-compose.yml:1`).

**File-storage volumes**
- `docker-compose.yml:57-61` mounts named volumes `media_data`, `static_data`,
  `docs_data`, `fastembed_cache`; declared at `63-68`. Rebuilds/updates reuse them.
- Non-regenerable content: `media_data` (uploads), `docs_data` (local docs, seeded from
  the image's `docs/` only when the volume is first created).
- Regenerable: `static_data` (collectstatic), `fastembed_cache` (re-download).
- Only volume-destructive commands remove them (`down -v`, `docker volume rm`,
  `docker volume prune`, or a Coolify volume-removal toggle).

**S3**
- `config/settings.py:232-241` — `DOCS_S3["ENABLED"] = bool(BUCKET)`.
- `apps/documentation/services/s3.py:59-63` — credentials are passed to boto3 only when
  **both** `ACCESS_KEY_ID` and `SECRET_ACCESS_KEY` are set; otherwise boto3 falls back to
  its default chain, so a partial config fails at request time, not startup.
- `docker-compose.yml:47-53` already passes `${DOCS_S3_*:-}` explicitly (blank = local).

## Decisions

| Decision | Choice |
| --- | --- |
| Postgres password source | Single `POSTGRES_PASSWORD`, used by `db` and `web` |
| Postgres strictness | Hard-required: `${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required (see .env.sample)}` |
| Coolify magic var | Remove all `SERVICE_PASSWORD_POSTGRES` usage |
| File volumes | Keep named volumes; no compose change; document safeguards + `docs_data` seeding caveat |
| S3 credentials | All-or-nothing guard: raise `ImproperlyConfigured` when bucket is set and exactly one of key/secret is set; both blank keeps the default/IAM-role chain |
| Rotation | Out of scope; document that the DB password is fixed at first init |

## Ordered tasks (atomic)

### A. PostgreSQL credentials

1. **`db` password source** — `docker-compose.yml:10`: replace
   `POSTGRES_PASSWORD: ${SERVICE_PASSWORD_POSTGRES}` with
   `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required (see .env.sample)}`.
   *Success:* with `POSTGRES_PASSWORD` set, `docker compose config` shows the same value
   on `db` and `web`.

2. **`web` connection string** — `docker-compose.yml:41`: replace the
   `${SERVICE_PASSWORD_POSTGRES}` segment of `DATABASE_URL` with the same
   `${POSTGRES_PASSWORD:?...}` expression; keep the rest of the URL unchanged.
   *Success:* `web`'s `DATABASE_URL` embeds the identical password used by `db`.

3. **Remove leftovers** — search the repo for `SERVICE_PASSWORD_POSTGRES`.
   *Success:* zero matches.

4. **`.env.sample` guidance** — near `POSTGRES_PASSWORD` (line 33): state it is set once
   before first start, must stay stable across updates, and that changing it after
   `pgdata` is initialized requires `ALTER USER ... WITH PASSWORD ...` inside the DB.
   Keep the placeholder in `DATABASE_URL` (line 28) matching.
   *Success:* sample warns the value is captured at first init.

5. **`README.md` DB note** — under Option B → "Persistent data" (around 199-207): note
   that `POSTGRES_PASSWORD` is captured when `pgdata` is first created and must stay
   stable; updating the app reuses the volume and does not reset it.
   *Success:* README states the password is fixed at first init.

### B. File-storage volumes

6. **Document persistence safeguards** — extend the README "Persistent data" section:
   named volumes survive rebuilds; they are removed **only** by `docker compose down -v`,
   `docker volume rm <name>`, or `docker volume prune`. List the non-regenerable volumes
   (`pgdata`, `media_data`, `docs_data`) and the regenerable ones (`static_data`,
   `fastembed_cache`). State: never run `down -v` on production; in Coolify keep the
   "remove/delete volumes on redeploy" option disabled.
   *Success:* README names each volume and the exact destructive commands to avoid.

7. **Document the `docs_data` seeding caveat** — in the same section, note that
   `docs_data` is seeded from the image's `docs/` **only** when the volume is first
   created, so later image updates do not refresh already-seeded content; use
   `sync_docs` / re-import, or a bind mount, if bundled `docs/` must track the image.
   *Success:* README explains why updated bundled docs may not appear.

   *(No `docker-compose.yml` change for B — volumes are already correct.)*

### C. S3 credentials

8. **All-or-nothing guard** — in `config/settings.py` immediately after the `DOCS_S3`
   dict / `ENABLED` assignment (around line 241), add: if `DOCS_S3["ENABLED"]` and exactly
   one of `ACCESS_KEY_ID` / `SECRET_ACCESS_KEY` is non-empty, raise
   `django.core.exceptions.ImproperlyConfigured` naming both variables. Both blank must
   remain valid (default/IAM-role chain); both set remains valid.
   *Success:* with `DOCS_S3_BUCKET` set and only the access key set, Django startup raises
   with a clear message; with both or neither set, startup is unaffected.

9. **`.env.sample` S3 guidance** — in the S3 block (lines 111-120): state that when
   `DOCS_S3_BUCKET` is set, `DOCS_S3_ACCESS_KEY_ID` and `DOCS_S3_SECRET_ACCESS_KEY` must
   be provided **together**, or both left blank to use the instance/default credential
   chain.
   *Success:* sample documents the all-or-nothing rule.

10. **As-built change note** — add
    `docs/Developer/changes/<timestamp>-harden-credentials-and-file-persistence.md`
    following the existing dated-change convention, recording: the Postgres variable
    rename + fail-fast choice, the documented volume safeguards, and the S3 guard.
    *Success:* the change note matches the shipped behavior.

## Risks / notes

- **Existing `pgdata` volume:** if `POSTGRES_PASSWORD` differs from the value used at
  initdb, auth fails after the change. Set it to the **existing** password or run
  `ALTER USER` in psql. This plan does not rotate the password.
- **Fail-fast by design:** an update/deploy without `POSTGRES_PASSWORD` now fails at
  `docker compose config`/`up` time. Locally a `.env` is required; in Coolify the
  variable must be set in the resource UI.
- **S3 guard scope:** it only catches a partial pair; it cannot detect a valid-but-wrong
  credential. It intentionally preserves boto3's default chain for role-based setups.
- **`docs_data` seeding** is existing Docker behavior, not caused by this change; the
  fix here is documentation only.
- **No schema impact:** model field conventions and migrations are unaffected.

## Validation (user-run — the agent does not test)

1. `docker compose config` with `POSTGRES_PASSWORD` set — `db` and `web` show the same
   password.
2. Unset `POSTGRES_PASSWORD` — `docker compose config` errors with the fail-fast message.
3. `docker compose up -d` on the existing stack — `web` connects to `db`; rows intact.
4. `docker compose exec db psql -U <user> -d <db> -c "\dt"` lists Django tables.
5. `docker compose restart web` (no `-v`) — `docs_data` files under `/app/docs` and
   `media_data` uploads are still present.
6. With `DOCS_S3_BUCKET` set and only `DOCS_S3_ACCESS_KEY_ID` set, Django startup raises
   `ImproperlyConfigured`; with both or neither set, startup is unchanged.
7. Repo search confirms no `SERVICE_PASSWORD_POSTGRES` remains.

## Out of scope

- Automated backup/restore tooling (pg_dump schedules, S3 backups).
- Password rotation tooling or a role-password migration.
- Changing volume names, adding bind mounts, or modifying other services.
- Application/business-logic changes beyond the S3 config guard.
- Agent-run testing (the user is solely responsible for testing and validation).
