# Planure: Site Favicon Upload

## Feature Overview

Let an admin upload a **favicon** for the documentation site, and render it as the
browser tab icon on every page.

- **Business objective:** replace the default browser icon with the organization's own
  brand mark without a code deploy.
- **Problem being solved:** there is no favicon today and no way to configure one from
  the admin. `HomePage` already acts as the site-wide branding singleton.
- **Expected user outcome / success criteria:**
  - Admin → Home page → Branding exposes a `favicon` image field (upload/clear).
  - When set, every page (`/`, docs pages, 404, account login/signup) serves that image
    at `GET /favicon.ico`.
  - When unset, `/favicon.ico` returns 404 and templates degrade silently.

## Components & Modules Involved

**Files changed**
- `apps/documentation/models.py` — add `HomePage.favicon` (`ImageField`,
  `upload_to="documentation/branding/"`, `blank`, `null`, `verbose_name="favicon"`).
- `apps/documentation/migrations/0011_homepage_favicon.py` — new migration.
- `apps/documentation/admin.py` — add `favicon` to the `HomePageAdmin` Branding fieldset.
- `apps/documentation/context_processors.py` — NEW `site_branding` (exposes `home` to all
  templates, including allauth/admin pages that use `base.html`).
- `config/settings.py` — register `documentation.context_processors.site_branding`.
- `apps/documentation/views.py` — NEW `FaviconView` serving the uploaded file (or 404).
- `config/urls.py` — route `favicon.ico` → `FaviconView` (`name="favicon"`).
- `apps/documentation/templates/documentation/base.html` — `<link rel="icon">`.
- `apps/documentation/templates/documentation/home.html` — `<link rel="icon">`.

**External dependencies:** none new (Pillow already required for existing `ImageField`s).

## High-Level Implementation Steps

1. **Add `HomePage.favicon` field** — `ImageField` per repo field convention. Success:
   field appears in the model; migration generated.
2. **Create migration `0011_homepage_favicon`** — `AddField` on `homepage`. Success:
   `migrate` applies cleanly (user-run).
3. **Expose the field in admin** — add `favicon` to the Branding fieldset. Success: admin
   Home page form shows an upload/clear widget.
4. **Add `site_branding` context processor** — return `{"home": HomePage.load()}`. Success:
   `home` available in every template rendering `base.html`.
5. **Register the context processor** in `settings.py` TEMPLATES. Success: no
   template errors on account/admin pages.
6. **Add `FaviconView`** — load `HomePage`, stream `home.favicon` with its content type
   and a cache header; raise `Http404` when unset. Success: `/favicon.ico` serves the
   uploaded image.
7. **Route `favicon.ico`** in `config/urls.py`. Success: URL name `favicon` resolves.
8. **Render `<link rel="icon" href="{% url 'favicon' %}">`** in `base.html` and
   `home.html`. Success: browser tab shows the uploaded icon.

## Validation (user-run — agent does not test)

1. `python manage.py migrate`.
2. In admin, open **Home page → Branding**, upload a PNG/ICO/SVG favicon, save.
3. Visit `/` and a docs page, hard-reload, confirm the tab icon.
4. Clear the favicon and confirm `/favicon.ico` returns 404 and pages still load.
