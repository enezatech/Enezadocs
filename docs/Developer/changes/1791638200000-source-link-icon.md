---
menu name: Configurable Source Link & Icon
position: 14
---

# Change: Configurable source/website link and icon in the docs header

**Date:** 2026-10-10

## Goal

Let each documentation site point its header link at either an open-source page
(a GitHub repository) or a proprietary/external webpage, and let the header icon
be chosen (GitHub brand mark, Globe, External-link, Book, Code) instead of the
previously hard-coded GitHub mark that only appeared for GitHub sources.

## What changed

| Area | Change |
| --- | --- |
| Model | `DocumentationSite` gains `source_url` (blank `URLField`) and `source_icon` (`CharField` with a new `LinkIcon` `TextChoices`, default `github`), each with `verbose_name`. Migration `0014_documentationsite_source_icon_and_source_url.py`. |
| Resolution | `services/documentation.py` adds `source_link()` returning `{"url", "icon"}` or `None`: an explicit `source_url` always wins; otherwise GitHub sources keep the derived repository URL with the `github` icon; every other case returns `None`. `source_home_url()` is kept. |
| View context | `views.py` `_context` exposes `source_link` instead of the old `github_url`. |
| Icon tag | `templatetags/home_tags.py` adds `external-link` and `book` stroke paths, a filled `github` brand path, `link_icon_svg(key, size)` (filled GitHub mark, else the existing stroke rendering) and `link_icon_label(key)` for the aria-label. |
| Header template | `templates/documentation/base.html` guards on `{% if source_link.url %}`, links `{{ source_link.url }}`, renders `{% link_icon_svg source_link.icon %}`, and sets `aria-label` via `{% link_icon_label source_link.icon %}`. |
| Admin | `DocumentationSiteAdmin` shows `source_icon` in `list_display` and groups `source_url`/`source_icon` under a "Source link" fieldset. Saving already clears the home cache. |

## Notes

- Blank `source_url` preserves today's behaviour for `GITHUB` sources (derived repo tree URL + GitHub icon); a non-GitHub source with a blank URL renders no header link.
- Icons: `github` (filled brand mark), `globe`, `external-link`, `book`, `code`. Aria-labels: `github` → "View source on GitHub", `globe` → "Visit website", `external-link` → "Open external link", `book` → "Read the docs", `code` → "View source".
- No data migration: `source_icon` defaults to `github`, so existing GitHub sites are visually unchanged.
- Scope is the docs header only; home-page cards / featured links still use the separate `Icon` choices and are out of scope. Custom uploaded image icons and per-source configuration are also out of scope.
- Agent does not test; the user is solely responsible for testing and validation.

## User validation

1. `python manage.py makemigrations documentation` (no-op if `0014` already present) then `migrate` on a DB copy.
2. GitHub site with blank `source_url` — header link is the repo tree URL with the GitHub icon.
3. Any site with `source_url` set (e.g. `https://example.com`) — header links there and the icon follows `source_icon`.
4. Non-GitHub site with blank `source_url` — no header link/icon.
5. Cycle through all five `source_icon` values and confirm the glyph and aria-label.
