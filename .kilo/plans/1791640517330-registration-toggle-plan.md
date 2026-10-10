# Registration Toggle (enable/disable new-user sign-up)

## Goal

Add a site-wide on/off switch that controls whether **new user accounts** can be
created. When **OFF**, no new account can be created by email/password signup or by a
first-time GitHub/Google sign-in; **existing** users keep signing in normally (email and
social). When **ON** (default), behavior is unchanged.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Control surface | `HomePage.allow_registration` `BooleanField` (default `True`), edited in the Django admin **Home page** form. |
| Scope of "off" | Blocks **all new-account creation**: email signup + first-time social signup. Existing users log in unaffected. |
| Enforcement point | Custom allauth account adapter overriding `is_open_for_signup`. `DefaultSocialAccountAdapter.is_open_for_signup` delegates to the account adapter, so one override covers both email and social new-signup paths. |
| Blocked UX | allauth renders a branded `account/signup_closed.html`; signup CTAs hidden in templates. Social sign-in buttons stay on the login page so existing social users can log in. |
| Default value | `True` (open). A missing `HomePage` row (`HomePage.load()` creates it) also means open. |
| Cache consistency | `allow_registration` rides along with the cached `HomePage`; `HomePageAdmin.save_related` already calls `clear_home_cache()`, so toggling takes effect immediately. |

## Verified behavior (allauth 65.19.2)

- `apps/documentation` uses django-allauth 65.19.2; signup served at `/accounts/signup/`.
- `allauth.account.mixins.CloseableSignupMixin.dispatch` calls `is_open_for_signup` and,
  when `False`, renders `account/signup_closed.html`.
- `allauth.socialaccount.internal.flows.signup.process_signup` raises
  `SignupClosedException` → `internal/flows/login.py` renders
  `account/signup_closed.html`; `sociallogin.is_existing` (returning users) skips the check.
- Setting key is `ACCOUNT_ADAPTER` (`allauth.account.app_settings.ADAPTER` → `_setting("ADAPTER", "allauth.account.adapter.DefaultAccountAdapter")`).

## Components & modules involved

**Files changed**
- `apps/documentation/models.py` — add `allow_registration` field to `HomePage`.
- `apps/documentation/migrations/0015_homepage_allow_registration.py` — NEW (generated).
- `apps/documentation/adapters.py` — NEW: `DocumentationAccountAdapter`.
- `config/settings.py` — point `ACCOUNT_ADAPTER` at the custom adapter.
- `apps/documentation/admin.py` — expose `allow_registration` in `HomePageAdmin.fieldsets`.
- `templates/account/signup_closed.html` — NEW branded "registration closed" page.
- `apps/documentation/templates/documentation/home.html` — hide signup CTAs when off.
- `templates/account/login.html` — hide the "Create an account" link when off.

**Unchanged** — social providers config, login flow, `signup.html` (unreachable when off),
`base.html` (only shows sign-in), MCP, search, sync.

## Implementation steps

1. **models.py — `HomePage`**: add, in the required field style (own line, `verbose_name`,
   aligned close paren):
   ```python
   allow_registration = models.BooleanField(
       default=True,
       verbose_name="allow registration",
       help_text="When disabled, new accounts cannot be created (email or social). Existing users can still sign in.",
   )
   ```
   Place it near the top of `HomePage` (e.g. after `brand_name`).

2. **Migration**: run `python manage.py makemigrations documentation` →
   `0015_homepage_allow_registration.py` (depends on `0014_*`).

3. **adapters.py (NEW, module `documentation.adapters`)**:
   ```python
   from allauth.account.adapter import DefaultAccountAdapter


   class DocumentationAccountAdapter(DefaultAccountAdapter):
       def is_open_for_signup(self, request):
           from .models import HomePage

           return HomePage.load().allow_registration
   ```
   Lazy-import `HomePage` inside the method to avoid app-registry boot issues.

4. **settings.py**: add near the other `ACCOUNT_*` settings:
   ```python
   ACCOUNT_ADAPTER = "documentation.adapters.DocumentationAccountAdapter"
   ```
   Do **not** set `SOCIALACCOUNT_ADAPTER`; the default social adapter already delegates.

5. **admin.py — `HomePageAdmin.fieldsets`**: add a fieldset, e.g.
   `("Registration", {"fields": ("allow_registration",)})`. No other admin change needed;
   `save_related` already clears the home cache.

6. **templates/account/signup_closed.html (NEW)**: extend `documentation/base.html`, match
   the card styling of `login.html`/`signup.html`; show a message that registration is
   disabled and a link to `{% url 'account_login' %}`.

7. **Template CTAs**: wrap the signup links in `{% if home.allow_registration %}`
   - `apps/documentation/templates/documentation/home.html`
     - mobile drawer "Create account" (currently ~line 102)
     - footer "Create account" (currently ~line 370)
   - `templates/account/login.html`
     - "New here? Create an account" block (currently ~line 58)
   Leave the social sign-in buttons and the sign-in links untouched.

8. **(Optional) README.md**: note the toggle under the "Authentication" feature bullet.

## Validation (user-run — the agent does not test)

1. Apply migration: `python manage.py migrate`.
2. Admin → **Home page** → **Registration** → leave `allow registration` checked.
   - Signup works as before (email and a first-time social sign-in).
   - Signup CTA visible on home and login pages.
3. Uncheck `allow registration` and save.
   - Home and login pages no longer show "Create account".
   - `GET /accounts/signup/` renders the branded closed page.
   - A first-time GitHub/Google sign-in renders the closed page (no account created).
   - An **existing** user can still sign in via email and via GitHub/Google.
4. Re-check and save → signup link and page are available again.

## Risks / notes

- Turning the switch **off does not deactivate or delete existing users**; it only blocks
  new account creation.
- If a `HomePage` row is absent, `HomePage.load()` creates it with `allow_registration=True`
  (registration stays open by default).
- Social providers remain configured while off; first-time social attempts show the closed
  page rather than an error.
- The cached `HomePage` instance drives the template flag; the admin save clears the cache,
  so no manual cache purge is required.

## Out of scope

- Deactivating/removing existing accounts.
- Per-role or per-email-domain signup rules.
- Approval-queue / invite-only signup.
- Changes to the login page for social-only scenarios or to `SOCIALACCOUNT_PROVIDERS`.
- Agent-run testing.
