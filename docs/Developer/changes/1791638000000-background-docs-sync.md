---
menu name: Background Documentation Sync
position: 12
---

# Change: Background documentation sync via Django Tasks

**Date:** 2026-10-10

## Goal

Move the admin **Sync documentation** action off the request thread. It used to
call `sync_source()` inline (`admin.py`), doing blocking GitHub HTTP calls plus a
full search/embedding index rebuild on the web worker — so the admin request
stalled for the whole sync. The sync now runs as a queued task executed by a
separate database worker.

## What changed

| Area | Change |
| --- | --- |
| Dependency | `requirements.txt` adds `django-tasks-db>=0.12` (database-backed backend for Django 6.1's built-in `django.tasks`, reusing the existing DB; no broker). |
| Settings | `config/settings.py` adds `"django_tasks_db"` to `INSTALLED_APPS` and a `TASKS` dict: `DatabaseBackend` with queues `["default", "sync"]`. Used in **all** environments, including local `DEBUG`; there is no inline fallback. |
| Task | New `apps/documentation/tasks.py` defines module-level `sync_source_task(source_id)` on queue `sync`. It re-fetches the source by PK, sets `last_sync_status="running"`, delegates to `sync_source()` (which records `ok`/`error`), and re-raises an unexpected exception after marking `error` so the task result is failed. |
| Enqueue + dedup | `services/sync.py` adds `enqueue_source_sync(source)`: skips a source that already has a `READY`/`RUNNING` `DBTaskResult` for this task, otherwise sets `last_sync_status="queued"`, enqueues, and returns `True`/`False`. On enqueue failure the previous status is restored. |
| Admin action | `admin.py` `sync_documentation` enqueues instead of syncing inline and reports how many were queued vs. already in flight. |
| Worker script | New `docker/worker.sh` runs `migrate`, `createcachetable`, then `exec python manage.py db_worker --queue-name=sync`. `Dockerfile` normalizes line endings and marks it executable. |
| Compose service | `docker-compose.yml` adds a `worker` service (same image, `restart: unless-stopped`, same DB settings, `depends_on: db healthy`) sharing the `media_data` / `docs_data` / `fastembed_cache` volumes so syncs read the same content tree and embedding cache as `web`. |
| Docs | `README.md` documents the worker, the local-dev worker command, and the three-service compose stack. |

## Notes

- Task arguments are JSON-round-tripped, so only the **source PK (int)** is passed; the worker re-fetches the model.
- Dedup inspects the in-flight `DBTaskResult` rows' stored args via `_result_targets_source()`, matching `task_path` ending in `sync_source_task`.
- `last_sync_status` transitions `queued → running → ok`/`error`; `last_sync_error` is set on failure.
- Out of scope and still synchronous: markdown upload index rebuild, the `import_structure` admin action, the `sync_docs` management command, and MCP token `last_used_at` writes.
- `DBTaskResult` rows accumulate; a periodic cleanup is a follow-up (django-tasks-db may ship a cleanup command — verify).
- If the worker is down, a source stays `queued`; if it dies mid-task, `last_sync_status` can stay `running`.
- Requires `python manage.py migrate` to create the `django_tasks_db` tables.
- Agent does not test; the user is solely responsible for testing and validation.

## User validation

1. `pip install -r requirements.txt` then `python manage.py migrate` — `django_tasks_db` tables exist.
2. Start `python manage.py db_worker --queue-name=sync` and the web server.
3. In admin, select a GitHub source → **Sync documentation**. The page returns immediately and `last_sync_status` becomes `queued`.
4. Worker log shows the task; status becomes `running` then `ok` (or `error` with `last_sync_error` set).
5. Trigger the action again while the first sync is in flight — it reports the source as "already queued or running" and creates no second in-flight row.
6. `docker compose up -d` starts `web` and `worker`; repeat steps 3–5 against the containers.
7. With the worker stopped, the admin request still returns immediately and the source stays `queued` (no GitHub calls during the request).
