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
    "external-link": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "book": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
}

GITHUB_PATH = (
    '<path d="M12 .5C5.6.5.5 5.6.5 12c0 5.1 3.3 9.4 7.9 10.9.6.1.8-.3.8-.6v-2'
    'c-3.2.7-3.9-1.4-3.9-1.4-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 '
    '1.2.1 1.8 1.2 1.8 1.2 1 .1 1.8 1.9 1.8 1.9 1.7 2.4 4.3 1.7 5.4 '
    '1.3.1-1 .4-1.7.7-2.1-2.6-.3-5.3-1.3-5.3-5.8 0-1.3.5-2.3 1.2-3.2'
    '-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 0 1 5.8 0C18.3 4.9 '
    '19.3 5.2 19.3 5.2c.6 1.5.2 2.8.1 3.1.7.9 1.2 1.9 1.2 3.2 0 '
    '4.5-2.7 5.5-5.3 5.8.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A11.5 11.5 '
    '0 0 0 23.5 12C23.5 5.6 18.4.5 12 .5Z"/>'
)

LINK_ICON_LABELS = {
    "github": "View source on GitHub",
    "globe": "Visit website",
    "external-link": "Open external link",
    "book": "Read the docs",
    "code": "View source",
}


@register.simple_tag
def icon_svg(key, size=20):
    path = ICON_PATHS.get(key or "", ICON_PATHS["layers"])
    return mark_safe(
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round">{path}</svg>'
    )


@register.simple_tag
def link_icon_svg(key, size=20):
    if key == "github":
        return mark_safe(
            f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="currentColor">{GITHUB_PATH}</svg>'
        )
    return icon_svg(key, size)


@register.simple_tag
def link_icon_label(key):
    return LINK_ICON_LABELS.get(key or "", "Open link")


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
