# Planure: Reusable GitHub Credentials for Private Repos

## Feature Overview

Most documentation sources live in **private** GitHub repositories. Today the app can
only read GitHub via a single global `GITHUB_TOKEN` environment variable
(`apps/documentation/services/github.py:24`), so there is no way to store per-repo or
shared credentials through the app. This feature adds a **reusable `GitHubCredential`**
record whose token is encrypted at rest, and lets each `GitHubDocumentationSource`
reference one credential. A credential can be shared by many sources/repos, and the
existing `GITHUB_TOKEN` env var remains as a fallback.

Success criteria: an admin can create one credential (a GitHub personal access token)
and attach it to any number of GitHub sources; private-repo docs sync and render
correctly; the token is never stored in plaintext and never leaks into HTML, logs, or
admin lists.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Credential model | New reusable `GitHubCredential` model (`name` + encrypted `token`). |
| Attachment | `GitHubDocumentationSource.credential` — nullable FK, `on_delete=SET_NULL`. |
| Encryption | Custom Fernet field; key derived from Django `SECRET_KEY` (SHA-256 → urlsafe base64). No new field library. |
| Token format | GitHub PAT as bearer token (`Authorization: Bearer <token>`). Works for classic PAT (`repo` scope) and fine-grained PAT (`Contents: Read` + `Metadata: Read`). |
| Resolution precedence | Source credential if set and non-empty, else `settings.GITHUB_TOKEN`. |
| Env fallback | `GITHUB_TOKEN` env var is kept unchanged. |
| Admin UX | `GitHubCredentialAdmin` with a masked, write-only token input; re-saving without a new token preserves the stored token. |
| Dependency | `cryptography` (already installed transitively via allauth's PyJWT); pinned explicitly in `requirements.txt`. |

## Components & modules involved

**Files changed**
- `apps/documentation/services/crypto.py` — NEW: `encrypt_token`, `decrypt_token`, Fernet key derivation.
- `apps/documentation/fields.py` — NEW: `EncryptedTextField` model field.
- `apps/documentation/models.py` — `GitHubCredential` model + `credential` FK on `GitHubDocumentationSource`.
- `apps/documentation/migrations/0005_githubcredential_githubdocumentationsource_credential.py` — generated migration.
- `apps/documentation/services/github.py` — `GitHubClient._headers()` credential resolution.
- `apps/documentation/admin.py` — register `GitHubCredential` with masked token form.
- `requirements.txt` — add explicit `cryptography>=42`.

**Unchanged** — `settings.py` (`GITHUB_TOKEN` fallback stays), `sync.py`, `factory.py`,
`documentation.py`, providers other than header resolution, templates, views, assets.

## Implementation steps

1. **services/crypto.py** — add `_fernet()` that derives a Fernet key from
   `settings.SECRET_KEY` (`hashlib.sha256(secret.encode()).digest()` →
   `base64.urlsafe_b64encode`), and `encrypt_token(value)` / `decrypt_token(ciphertext)`.
   Empty string stays empty; `decrypt_token` returns `""` on any failure (e.g. changed
   `SECRET_KEY`) instead of raising.

2. **fields.py** — add `EncryptedTextField(models.TextField)` that encrypts on
   `get_prep_value` and decrypts on `from_db_value`/`to_python` via `services.crypto`.

3. **models.py** —
   - Add `GitHubCredential` with `name` (CharField), `token` (`EncryptedTextField`),
     `created_at` (auto_now_add), `updated_at` (auto_now). Every field on its own line,
     each with `verbose_name`, aligned closing `)`. `__str__` returns `name` only (never
     the token).
   - Add `credential = models.ForeignKey(GitHubCredential, on_delete=models.SET_NULL,
     null=True, blank=True, related_name="github_sources", verbose_name="credential")`
     to `GitHubDocumentationSource`, following the same field conventions.

4. **Migration** — `python manage.py makemigrations documentation` → generates
   `0005_githubcredential_githubdocumentationsource_credential.py`.

5. **services/github.py** — update `GitHubClient._headers()`: try
   `self.config.credential` (guarded with `try/except` for a deleted row); if present,
   decrypt its `token`; if that yields a non-empty string use it, otherwise fall back to
   `settings.GITHUB_TOKEN`. No other read path changes — tree/commit/raw/asset all flow
   through `_headers()`.

6. **admin.py** — register `GitHubCredentialAdmin` with `list_display`
   (`name`, `created_at`, `updated_at`) and a custom `ModelForm` whose `token` is a
   `forms.CharField(widget=PasswordInput, required=False, help_text=...)`; on save, set
   the encrypted token only when a new value is supplied (blank ⇒ keep existing token).
   The `credential` FK auto-appears on `GitHubDocumentationSourceInline`.

7. **requirements.txt** — add `cryptography>=42` (now a direct dependency).

## Validation (user-run — agent does not test)

1. `python manage.py makemigrations documentation` and `python manage.py migrate`.
2. Admin → create a `GitHubCredential` with a real PAT; confirm the field is masked and
   the token never appears in the changelist or object `__str__`.
3. Edit the credential without re-entering the token; confirm the stored token survives.
4. Attach the credential to a `GitHubDocumentationSource` pointing at a **private** repo;
   run sync (`manage.py sync_docs`) and open the site — docs render, nav, assets, search.
5. Create a second GitHub source pointing at another private repo and attach the **same**
   credential; confirm reuse works.
6. Confirm fallback: a GitHub source with no credential still authenticates via the
   `GITHUB_TOKEN` env var.
7. Confirm no token appears in HTML source, request logs, or admin pages.

## Risks / notes

- Rotating `SECRET_KEY` invalidates stored ciphertext; `decrypt_token` returns `""`,
  causing graceful fallback to `GITHUB_TOKEN` (or unauthenticated requests). Re-enter the
  token to restore private access.
- Token secrecy: never include the token in `__str__`, error messages, logs, or templates.
- `cryptography` must remain installed (it is present in `env/`); the explicit
  `requirements.txt` pin guards against it being dropped as a transitive dep.

## Out of scope

- GitHub App / installation-token auth; token rotation UI; per-repo scope validation;
  webhook-driven sync; credential audit/history; masking outside the admin.
