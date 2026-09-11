# Change: Admin favicon upload

**Date:** 2026-09-11

## Goal

Allow an admin to upload a site favicon and render it as the browser tab icon on all
pages, without a code deploy.

## What changed

| Area | Change |
| --- | --- |
| Model | `HomePage.favicon` (`ImageField`, `upload_to="documentation/branding/"`, optional). |
| Migration | `apps/documentation/migrations/0011_homepage_favicon.py`. |
| Admin | `favicon` added to the `HomePageAdmin` **Branding** fieldset. |
| Context | New `documentation.context_processors.site_branding` exposes `home` to every template (registered in `config/settings.py`), so `base.html` pages rendered by allauth/admin also see it. |
| Serving | New `FaviconView` streams the uploaded file at `GET /favicon.ico` (`name="favicon"`) with `Cache-Control: public, max-age=86400`; returns 404 when unset. Uses a view (not `MEDIA_URL`) because media is not served by the current ASGI/whitenoise deployment. |
| Templates | `<link rel="icon" href="{% url 'favicon' %}">` added to `base.html` and `home.html`. |

## Notes

- Follows the repo model-field convention (one field per line, `verbose_name`, closing
  paren on its own line).
- The uploaded image is served through Django rather than `/media/`, matching the
  existing `AssetProxyView` pattern and avoiding media-serving configuration.

## User validation

1. `python manage.py migrate`.
2. Admin → **Home page** → Branding → upload a favicon → save.
3. Reload `/` and a docs page; confirm the tab icon. Clear the favicon and confirm pages
   still load.
