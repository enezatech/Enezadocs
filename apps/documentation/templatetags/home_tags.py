from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

from documentation.services.navigation import slugify_path

register = template.Library()

ICON_PATHS = {
    "layers": '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
    "code": '<path d="m8 3-5 9 5 9"/><path d="m16 3 5 9-5 9"/>',
    "terminal": '<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
    "shield": '<path d="M12 3l7 3v5c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6l7-3Z"/><path d="m9 12 2 2 4-4"/>',
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z"/>',
    "card": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18"/>',
    "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5V8Z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>',
}


@register.simple_tag
def icon_svg(key, size=20):
    path = ICON_PATHS.get(key or "", ICON_PATHS["layers"])
    return mark_safe(
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round">{path}</svg>'
    )


@register.filter
def doc_url(path):
    return slugify_path(path)


@register.filter
def compact_time(value):
    if value is None:
        return ""
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    seconds = (timezone.now() - value).total_seconds()
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours // 24)
    if days < 7:
        return f"{days}d ago"
    weeks = int(days // 7)
    if weeks < 5:
        return f"{weeks}w ago"
    months = int(days // 30)
    if months < 12:
        return f"{months}mo ago"
    years = int(days // 365)
    return f"{years}y ago"
