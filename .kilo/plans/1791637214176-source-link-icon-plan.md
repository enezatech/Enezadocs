# Plan: Configurable source/website link and icon in docs header

## Goal

Let each documentation site point its header link at either an open-source page
(GitHub repo) or a proprietary/external webpage, and let the header icon be
chosen (GitHub brand mark, Globe, External-link, Book, Code) instead of the
currently hard-coded GitHub mark.

## Current behavior (evidence)

- Header renders a hard-coded GitHub SVG and uses `github_url`:
  `apps/documentation/templates/documentation/base.html:55-59`.
- `github_url` is injected per document page from `service.source_home_url()`:
  `apps/documentation/views.py:251`.
- `source_home_url()` returns a URL only when the source type is `GITHUB`
  (derived `https://github.com/<owner>/<repo>/tree/<branch>/<root_path>`);
  otherwise `None`: `apps/documentation/services/documentation.py:305-314`.
- `DocumentationSite` already has an `Icon` TextChoices set (for cards):
  `apps/documentation/models.py:159-192`; icon rendering goes through the
  `icon_svg` tag with stroke-style paths: `apps/documentation/templatetags/home_tags.py:9-28`.
- Latest migration is `0013_documentationsearchdocument_nav_metadata.py`;
  next is `0014`.

## Decisions (confirmed)

- Configure per site on `DocumentationSite` (not on the source).
- `source_url` blank => fall back to the auto-derived GitHub URL for `GITHUB`
  sources (preserves today's behavior); for non-GitHub sources a blank URL shows
  no icon.
- Selectable icons: `github` (filled brand mark), `globe`, `external-link`,
  `book`, `code`.
- Scope: the docs header only (home-page cards are out of scope).

## Atomic tasks

1. **Model fields** — `apps/documentation/models.py`, `DocumentationSite`:
   - Add inner `LinkIcon(models.TextChoices)`: `GITHUB="github"`, `GLOBE="globe"`,
     `EXTERNAL_LINK="external-link"`, `BOOK="book"`, `CODE="code"`.
   - Add `source_url = models.URLField(blank=True, verbose_name="source link", help_text="Open-source repo or product webpage. Leave blank to use the GitHub repository URL for GitHub sources.")`.
   - Add `source_icon = models.CharField(max_length=20, choices=LinkIcon.choices, default=LinkIcon.GITHUB, verbose_name="source link icon")`.
   - Follow repo field conventions: one field per line, every field has
     `verbose_name`, multi-line declarations close the `)` on its own line.
   - Success: `python manage.py makemigrations documentation` creates `0014_*`.

2. **Migration** — create `apps/documentation/migrations/0014_*.py` (auto-generated)
   adding `source_url` and `source_icon` to `documentationsite`.
   - Success: `python manage.py migrate` applies cleanly on a copy of `db.sqlite3`.

3. **Resolve link + icon** — `apps/documentation/services/documentation.py`:
   - Add `source_link()` returning a small dict/`None`, e.g.
     `{"url": ..., "icon": ...}`:
     - If `self.site.source_url` is set => `{"url": source_url, "icon": source_icon}`.
     - Else if `source_type == "GITHUB"` and a `github` config exists => derived
       URL (existing logic) with icon `github`.
     - Else => `None`.
   - Keep `source_home_url()` (or delegate it to `source_link()`) so nothing else
     breaks; confirm with grep that only `views.py:251` consumes it.
   - Success: method returns the expected URL/icon for GitHub, non-GitHub with a
     URL, and non-GitHub without a URL.

4. **View context** — `apps/documentation/views.py:_context` (line ~243-252):
   - Replace `"github_url": service.source_home_url()` with
     `"source_link": service.source_link()` (rename the context key).
   - Success: rendered page exposes `source_link.url` / `source_link.icon`.

5. **Icon tag** — `apps/documentation/templatetags/home_tags.py`:
   - Add stroke paths for `external-link` and `book` to `ICON_PATHS`; keep
     `globe` and `code` as-is.
   - Add a simple tag `link_icon_svg(key, size=20)` that renders the `github`
     key with the filled brand path from `base.html:57` (`fill="currentColor"`,
     no stroke) and delegates everything else to the existing stroke rendering.
   - Success: header shows a filled GitHub mark for `github` and a matching
     stroke icon for the other keys.

6. **Header template** — `apps/documentation/templates/documentation/base.html:55-59`:
   - Guard on `{% if source_link.url %}`.
   - `href="{{ source_link.url }}"`.
   - Replace the inline `<svg>` with `{% link_icon_svg source_link.icon %}` (load
     the tag library if not already loaded).
   - Set `aria-label` from the icon: github -> "View source on GitHub",
     globe -> "Visit website", external-link -> "Open external link",
     book -> "Read the docs", code -> "View source".
   - Success: choosing each icon in admin renders the correct glyph and label.

7. **Admin** — `apps/documentation/admin.py`, `DocumentationSiteAdmin` (line ~222):
   - Ensure `source_url` and `source_icon` are editable (default ModelAdmin
     already includes them; optionally add `source_icon` to `list_editable` and
     `("name","slug","source","source_icon","enabled")` groups via a fieldset).
   - Saving already calls `clear_home_cache()` (`admin.py:242-244`); no extra work.
   - Success: admin site change form saves both fields without error.

## Validation (user is solely responsible for all testing)

- `python manage.py makemigrations documentation` then `migrate` on a DB copy.
- GitHub site, `source_url` blank => header link is the repo tree URL, GitHub icon.
- Any site with `source_url` set (e.g. `https://example.com`) => header links
  there; icon follows `source_icon`.
- Non-GitHub site with blank `source_url` => no header link/icon.
- Cycle through all five `source_icon` values and confirm glyph + aria-label.

## Risks / notes

- Context key rename (`github_url` -> `source_link`): only `base.html` and
  `views.py` reference it (grep-confirmed); update both together.
- The home-page card icons use the separate `Icon` choices at
  `models.py:159-192`; do not merge the two sets.
- No data migration needed; `source_icon` defaults to `github`, so existing
  GitHub sites are visually unchanged.

## Out of scope

- Home-page site cards / featured links pointing at `source_url`.
- Custom uploaded image icons.
- Per-source (shared) configuration.
