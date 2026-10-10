# Background documentation sync via Django Tasks

## Goal

Move the admin **"Sync documentation"** action off the request thread. The action currently calls `sync_source()` inline (`apps/documentation/admin.py:37-41`), which performs blocking GitHub HTTP calls plus a full search/embedding index rebuild on the web worker. Enqueue it as a Django Task executed by a separate database worker.

## Decisions (agreed)

- Use Django 6.1's built-in Tasks framework (`django.tasks`) with the third-party **`django-tasks-db`** `DatabaseBackend` (Postgres-backed, reuses the existing DB; no new broker).
- `DatabaseBackend` in **all** environments, including local DEBUG. Developers run `python manage.py db_worker` alongside the app; there is no inline/immediate fallback.
- Dedicated queue name `sync` for this task.
- On enqueue set `DocumentationSource.last_sync_status = "queued"`; the worker sets `"running"` at start and `"ok"`/`"error"` on completion (via existing `sync_source`).
- Deduplicate: skip a source that already has a `READY`/`RUNNING` `DBTaskResult` for the sync task.
- Scope is **only** the admin `sync_documentation` action. Out of scope (stay synchronous): markdown upload index rebuild (`admin.py:283-300`), `import_structure` action (`admin.py:44-58`), the `sync_docs` management command, and the MCP token `last_used_at` write.

## Key constraints

- Task arguments are passed through `json.dumps`/`json.loads`, so pass only the **source PK (int)**, never a model instance. The worker re-fetches the source.
- Django 6.1 provides **no production backend and no worker**; `db_worker` comes from `django-tasks-db`.

## Implementation tasks

### 1. Add dependency
- `requirements.txt`: add `django-tasks-db` (pin to a release compatible with Django 6.1; verify with `pip install`).

### 2. Configure settings — `config/settings.py`
- Add `"django_tasks_db"` to `INSTALLED_APPS` (near `"documentation"`).
- Add the `TASKS` setting:
  ```python
  TASKS = {
      "default": {
          "BACKEND": "django_tasks_db.DatabaseBackend",
          "QUEUES": ["default", "sync"],
      }
  }
  ```
- Success: `python manage.py migrate` creates the `django_tasks_db` tables (both SQLite and Postgres paths).

### 3. Define the task — new file `apps/documentation/tasks.py`
- Module-level task (required so `task_path` is importable in the worker):
  ```python
  from django.tasks import task


  @task(queue_name="sync")
  def sync_source_task(source_id: int) -> None:
      from documentation.models import DocumentationSource
      from documentation.services.sync import sync_source

      source = DocumentationSource.objects.filter(pk=source_id).first()
      if source is None:
          return
      source.last_sync_status = "running"
      source.save(update_fields=["last_sync_status"])
      sync_source(source)
  ```
- `sync_source` already catches provider/index errors and writes `last_sync_status`/`last_sync_error`, so it normally does not raise. Wrap the call so an unexpected exception still records `error` and then re-raises (so the `DBTaskResult` is marked failed).
- Success: `sync_source_task.enqueue(1)` returns a `TaskResult` without a serialization error.

### 4. Enqueue helper with dedup — `apps/documentation/services/sync.py`
- Add `enqueue_source_sync(source) -> bool`:
  1. If a `DBTaskResult` row with `status in ("READY", "RUNNING")` exists whose stored args contain `source.pk` for this task, return `False` (already in flight).
  2. Otherwise set `source.last_sync_status = "queued"`, save `update_fields=["last_sync_status"]`, call `sync_source_task.enqueue(source.pk)`, return `True`.
- **Verify the exact `task_path` value** `django-tasks-db` stores for `sync_source_task` (enqueue once in a Django shell and read `DBTaskResult.task_path`) before filtering on it; the implementer must confirm this string rather than guess it. If it is unreliable, fall back to filtering `READY`/`RUNNING` rows by inspecting `args_kwargs["args"]`/`["kwargs"]["source_id"]` in Python over the small in-flight set.
- Import the status enum from wherever `django-tasks-db` exposes it, or filter on the stored string values `"READY"`/`"RUNNING"` which avoids import-path guessing.
- Success: calling the helper twice for the same source returns `True` then `False`, and only one `READY` row exists.

### 5. Rewrite the admin action — `apps/documentation/admin.py`
- Import `enqueue_source_sync` from `documentation.services.sync` (drop the now-unused `sync_source` import; keep `invalidate_source`, `rebuild_index_for_source` used elsewhere).
- Replace `sync_documentation`:
  ```python
  @admin.action(description="Sync documentation")
  def sync_documentation(modeladmin, request, queryset):
      queued = skipped = 0
      for source in queryset:
          if enqueue_source_sync(source):
              queued += 1
          else:
              skipped += 1
      message = f"Queued {queued} source(s) for sync."
      if skipped:
          message += f" {skipped} already queued or running."
      modeladmin.message_user(request, message)
  ```
- Success: the admin action returns immediately (no GitHub calls in the request) and updates `last_sync_status` to `queued`.

### 6. Run the worker — deployment
- **New `docker/worker.sh`**: apply migrations (safe/idempotent, same as web) then exec the worker:
  ```sh
  #!/bin/sh
  set -e
  python manage.py migrate --noinput
  exec python manage.py db_worker --queue-name=sync
  ```
  Make it executable in the `Dockerfile` alongside `entrypoint.sh` (extend the existing `sed`/`chmod`/`chown` line at `Dockerfile:20-22`).
- **`docker-compose.yml`**: add a `worker` service built from the same image, `restart: unless-stopped`, same `env_file`/`environment` DB settings as `web` (`DB_ENGINE`, `DATABASE_URL`, `FASTEMBED_CACHE_PATH`), `depends_on: db: condition: service_healthy`, `entrypoint: ["/app/docker/worker.sh"]`, and the **same volumes the sync needs**: `docs_data:/app/docs`, `media_data:/app/media`, `fastembed_cache:/cache`. It must read the same content tree and embedding cache as `web`.
- Local dev: document running `python manage.py db_worker --queue-name=sync` in a second terminal; `runserver` alone will leave tasks queued.

### 7. Documentation
- `README.md`: add `db_worker` to the management commands list, note the new `worker` compose service, and add the local-dev worker step (section "Option A" step 7 area and "Option B" service list at line ~184-190).

## Validation (user-run)
1. `pip install -r requirements.txt` then `python manage.py migrate` — `django_tasks_db` tables exist.
2. Start `python manage.py db_worker --queue-name=sync` and `python manage.py runserver`.
3. In admin, select a GitHub source → **Sync documentation**. The page returns immediately and `last_sync_status` becomes `queued`.
4. Worker log shows the task; status transitions `queued → running → ok` (or `error` with `last_sync_error` set).
5. Click the action again while the first is in flight: second click reports the source as "already queued or running" and does not create a second in-flight row.
6. Docker: `docker compose up -d` starts `web` and `worker`; repeat steps 3–5 against the container.
7. Confirm no GitHub HTTP requests occur during the admin request (e.g. stop the worker and observe the source stays `queued`).

## Risks / notes
- Stale `queued`/`running`: if the worker is down or dies mid-task, `last_sync_status` can stay `running`. Consider a small admin note or a follow-up reconciliation; not required for this change.
- `DBTaskResult` rows accumulate; plan a periodic cleanup (django-tasks-db may ship a cleanup command — verify) as a follow-up.
- Different sources sync concurrently (separate tasks) — acceptable since `sync_source` is per-source and idempotent (guarded by commit SHA).
- Confirm `django-tasks-db` supports Django 6.1 at install time; if not, the fallback is a different third-party backend implementing the same `django.tasks` interface (task module and admin code stay unchanged).
