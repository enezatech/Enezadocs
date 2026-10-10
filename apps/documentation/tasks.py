from __future__ import annotations

from django.tasks import task


@task(queue_name="sync")
def sync_source_task(source_id: int) -> None:
    """Synchronize one documentation source in a background worker.

    Only the source PK is passed because task arguments make a JSON round-trip.
    The worker re-fetches the source, marks it ``running``, and delegates to
    ``sync_source``, which records ``ok``/``error`` on completion.
    """
    from documentation.models import DocumentationSource
    from documentation.services.sync import sync_source

    source = DocumentationSource.objects.filter(pk=source_id).first()
    if source is None:
        return

    source.last_sync_status = "running"
    source.last_sync_error = ""
    source.save(update_fields=["last_sync_status", "last_sync_error"])

    try:
        sync_source(source)
    except Exception as exc:
        source.last_sync_status = "error"
        source.last_sync_error = str(exc)
        source.save(update_fields=["last_sync_status", "last_sync_error"])
        raise
