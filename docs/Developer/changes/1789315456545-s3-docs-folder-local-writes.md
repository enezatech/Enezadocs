# Change: Reliable S3-vs-Local Documentation Storage

**Date:** 2026-09-13

## Goal

Make documentation storage deterministic and correctly S3-backed. Even with a
bucket configured, LOCAL sources fell back to local files and the admin kept
creating local `docs/` folders (e.g. `Developer/`, `Documentation/`,
`Documention/`).

Root causes fixed:

1. `_is_local_node()` treated every LOCAL source as filesystem-backed, so
   section/group create/delete still touched local disk.
2. `docker-compose.yml` re-declared `DOCS_S3_*` under `web.environment` with
   `${DOCS_S3_*:-}`. Service `environment` overrides `env_file`, and the
   `${...}` interpolation does not see variables a platform injects at
   container start, so an injected bucket could be blanked to empty and S3
   silently disabled.
3. There was no explicit S3/local selector; `DOCS_S3["ENABLED"]` came only from
   `bool(DOCS_S3_BUCKET)`.

## What changed

| Area | Change |
| --- | --- |
| Settings selector | `config/settings.py` resolves `DOCS_S3["ENABLED"]` from `DOCS_S3_ENABLED` (`1/true/yes/on` → force S3, `0/false/no/off` → force local, blank/unset → `bool(DOCS_S3_BUCKET)`). |
| Settings validation | With S3 enabled and a blank `DOCS_S3_BUCKET`, startup raises `ImproperlyConfigured`; the existing access-key/secret pairing guard is unchanged. |
| Admin folder ops | `apps/documentation/admin.py` keeps `_is_local_node()` as "belongs to a LOCAL source" and branches on `s3_enabled()`: local filesystem uses `mkdir`/`rmtree` as before; S3 creates/deletes a folder marker instead. |
| S3 folder markers | `apps/documentation/services/s3.py` adds `create_folder()` / `delete_folder()` writing a zero-byte `application/x-directory` object at `[PREFIX/]<path>/`; `DocumentationProvider` declares both methods. Creating a Section/Group now mirrors an object in the bucket. |
| Compose env | Removed the `DOCS_S3_*` entries from `web.environment`; values now come from the optional `env_file: .env` locally and from platform (Coolify) injection. A comment documents why they must not be re-declared. |
| Docs | `.env.sample` and the README env table document `DOCS_S3_ENABLED` and its precedence. |

## Notes

- Storage selection is deterministic for the process lifetime; there is no
  runtime bucket probe and no automatic fallback to local. If S3 is selected and
  unreachable, provider calls raise `ProviderUnavailable` rather than silently
  writing to disk, so content cannot be split between S3 and local storage.
- S3 has no real folders: `DOCS_S3_PREFIX` is the docs root and markdown is
  written as `[PREFIX/]<folder>/<name>.md`. To make the bucket mirror the admin
  tree, creating a Section/Group writes a zero-byte folder-marker object at
  `[PREFIX/]<path>/`; no local docs folder is created when S3 is selected.
- Deleting a section/group node removes only its folder marker; markdown
  objects under the prefix remain in the bucket (non-destructive).
- Forcing local with `DOCS_S3_ENABLED=0` requires a valid
  `LocalDocumentationSource.root_path`, and node creation validates it again.
- The `/app/docs` volume stays mounted even with S3 selected (unused for docs).
- Existing local folders predate this change and persist in the `docs_data`
  volume; remove them manually.
- No model, migration, or schema changes.
- Agent does not test; the user is solely responsible for testing and validation.

## User validation

1. Set `DOCS_S3_ENABLED=1`, `DOCS_S3_BUCKET`, `DOCS_S3_ENDPOINT_URL`,
   `DOCS_S3_ACCESS_KEY_ID`, `DOCS_S3_SECRET_ACCESS_KEY`, then
   `docker compose up -d --force-recreate web`.
2. `docker compose exec web python -c "import os; print(os.environ.get('DOCS_S3_ENABLED'), os.environ.get('DOCS_S3_BUCKET'))"`
   prints `1 <bucket>`.
3. `docker compose exec web python manage.py shell -c "from django.conf import settings; from documentation.services.s3 import s3_enabled; print(settings.DOCS_S3['ENABLED'], settings.DOCS_S3['BUCKET'], s3_enabled())"`
   prints `True <bucket> True`.
4. Remove leftover dirs under `/app/docs`, then create a Section and nested Group
   in the admin; `ls /app/docs` shows no new directories and the bucket shows a
   folder marker at `[DOCS_S3_PREFIX/]<path>/`.
5. Delete a Section/Group; its folder marker is removed, markdown objects under
   the prefix remain, and the local filesystem is unchanged.
6. Upload markdown into a Section/Group; the object appears in the bucket at
   `[DOCS_S3_PREFIX/]<folder>/<name>.md` with nothing written under `/app/docs`.
7. Set `DOCS_S3_ENABLED=0`, restart, and create a Section; the local folder is
   created as before.
8. `DOCS_S3_ENABLED=1` with a blank `DOCS_S3_BUCKET` makes startup raise
   `ImproperlyConfigured`.
