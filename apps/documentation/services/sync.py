from django.core.cache import cache
from django.utils import timezone

from documentation.models import DocumentationSource, GitHubDocumentationSource

from .github import GitHubClient
from .search import build_index


def invalidate_source(source):
    delete_pattern = getattr(cache, "delete_pattern", None)
    if delete_pattern is None:
        cache.clear()
        return
    delete_pattern(f"docs:source:{source.id}:asset:*")
    for site in source.sites.all():
        delete_pattern(f"docs:site:{site.id}:tree:*")
        delete_pattern(f"docs:site:{site.id}:document:*")


def rebuild_index_for_source(source):
    from .documentation import DocumentationService

    for site in source.sites.all():
        build_index(DocumentationService(site))
    # Indexing caches the tree while the fresh metadata rows do not yet exist;
    # drop those caches so the next request rebuilds from the persisted rows.
    invalidate_source(source)


def rebuild_structure_for_source(source, sites=None):
    """Recreate section/group rows from the provider's current folder tree.

    The provider tree is fetched once and shared across sites. ``sites``
    defaults to every site attached to the source.
    """
    from .factory import get_provider
    from .structure import rebuild_from_provider_tree

    provider = get_provider(source)
    tree = provider.get_tree()
    target_sites = source.sites.all() if sites is None else sites
    for site in target_sites:
        rebuild_from_provider_tree(site, tree)


def _structure_missing_sites(source):
    from documentation.models import DocumentationNode

    return [
        site
        for site in source.sites.all()
        if not site.nodes.filter(
            type__in=["section", "group"],
        ).exists()
    ]


def _result_targets_source(result, source_id):
    """True when a queued task result carries ``source_id`` as an argument."""
    payload = result.args_kwargs or {}
    if isinstance(payload, dict):
        args = payload.get("args") or []
        kwargs = payload.get("kwargs") or {}
    else:
        args = payload
        kwargs = {}
    if source_id in args:
        return True
    return kwargs.get("source_id") == source_id


def enqueue_source_sync(source):
    """Queue a background sync for ``source``.

    Returns ``True`` when a task was enqueued, or ``False`` when the source
    already has a ``READY``/``RUNNING`` sync task in flight.
    """
    from django_tasks_db.models import DBTaskResult

    in_flight = DBTaskResult.objects.filter(
        status__in=["READY", "RUNNING"],
        task_path__endswith="sync_source_task",
    )
    for result in in_flight:
        if _result_targets_source(result, source.pk):
            return False

    from documentation.tasks import sync_source_task

    previous_status = source.last_sync_status
    source.last_sync_status = "queued"
    source.save(update_fields=["last_sync_status"])
    try:
        sync_source_task.enqueue(source.pk)
    except Exception:
        source.last_sync_status = previous_status
        source.save(update_fields=["last_sync_status"])
        raise
    return True


def sync_source(source):
    if source.source_type != DocumentationSource.SourceType.GITHUB:
        source.last_sync_status = "ok"
        source.last_sync_error = ""
        source.last_sync_at = timezone.now()
        source.save(update_fields=["last_sync_status", "last_sync_error", "last_sync_at"])
        try:
            rebuild_index_for_source(source)
        except Exception as exc:
            source.last_sync_error = f"index rebuild failed: {exc}"
            source.save(update_fields=["last_sync_error"])
        return

    try:
        github = source.github
    except GitHubDocumentationSource.DoesNotExist:
        source.last_sync_status = "error"
        source.last_sync_error = "GitHub configuration missing"
        source.save(update_fields=["last_sync_status", "last_sync_error"])
        return

    client = GitHubClient(github)
    try:
        sha = client.get_latest_commit_sha()
    except Exception as exc:
        source.last_sync_status = "error"
        source.last_sync_error = str(exc)
        source.save(update_fields=["last_sync_status", "last_sync_error"])
        return

    missing_sites = _structure_missing_sites(source)
    if github.last_commit_sha and github.last_commit_sha == sha:
        if missing_sites:
            try:
                rebuild_structure_for_source(source, sites=missing_sites)
                rebuild_index_for_source(source)
            except Exception as exc:
                source.last_sync_status = "error"
                source.last_sync_error = str(exc)
                source.save(update_fields=["last_sync_status", "last_sync_error"])
                return
        source.last_sync_status = "ok"
        source.last_sync_error = ""
        source.last_sync_at = timezone.now()
        source.save(update_fields=["last_sync_status", "last_sync_error", "last_sync_at"])
        return

    invalidate_source(source)

    try:
        rebuild_structure_for_source(source)
        rebuild_index_for_source(source)
    except Exception as exc:
        source.last_sync_status = "error"
        source.last_sync_error = str(exc)
        source.save(update_fields=["last_sync_status", "last_sync_error"])
        return

    github.last_commit_sha = sha
    github.last_sync_at = timezone.now()
    github.save(update_fields=["last_commit_sha", "last_sync_at"])
    source.last_sync_status = "ok"
    source.last_sync_error = ""
    source.last_sync_at = timezone.now()
    source.save(update_fields=["last_sync_status", "last_sync_error", "last_sync_at"])


def sync_all():
    for source in DocumentationSource.objects.filter(enabled=True):
        sync_source(source)
