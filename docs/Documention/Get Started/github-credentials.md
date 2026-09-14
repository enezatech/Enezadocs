---
menu name: GitHub Credentials
position: 5
---

# Adding GitHub Credentials

GitHub documentation sources can read **private** repositories when you give them a
credential. A credential is a GitHub personal access token (PAT) that the app sends with
its GitHub API requests. This guide walks through creating the token, storing it in the
app, and attaching it to a source.

> Looking for GitHub **login (SSO)** instead? That is a separate setup using
> `GITHUB_CLIENT_ID` / `GITHUB_SECRET`. See [GitHub sign-in vs. docs access](#github-sign-in-vs-docs-access)
> at the end.

---

## 1. Before you start

You need:

- Admin access to the site (`/admin/`).
- A GitHub account with read access to the repository you want to document.
- The repository identified as `owner/repository` (for example `Eneza/enezadocs`).

If the repository is **public**, you can skip credentials entirely — but a token still
raises the API rate limit and is recommended for reliable syncing.

---

## 2. Create a personal access token

1. Open GitHub and go to **Settings → Developer settings → Personal access tokens**.
2. Choose either token type:

   | Token type | Required permissions |
   | --- | --- |
   | **Fine-grained** (recommended) | Repository access: the repo(s) to document. Permissions: **Contents: Read** and **Metadata: Read**. |
   | **Classic** | Scope: **repo** (for private repositories). |

3. Generate the token and **copy it immediately** — GitHub shows it only once.

Keep the token somewhere safe until the next step. Treat it like a password.

---

## 3. Store the credential in the app

One credential can be shared by any number of sources, so you only create it once per
token.

1. In the Django admin, open **GitHub credentials → Add**.
2. **Name** — a label you will recognize, for example `Docs bot` or `Eneza private repos`.
3. **Token** — paste the PAT from step 2. The field is masked as you type.
4. **Save**.

The changelist shows only the name and timestamps — the token is never displayed.

### Editing an existing credential

The token field is **write-only**: it is never shown again. To change other fields, just
edit them — leave the token blank to **keep the current token**. To **replace** the token,
paste a new value into the field and save. The placeholder reads
"blank keeps current token" as a reminder. You must paste the full token; partial values
are treated as a new token.

---

## 4. Attach the credential to a source

1. Open **Documentation sources** and select the GitHub source you want to use.
2. In the **GitHub documentation source** section, find the **Credential** dropdown.
3. Select the credential you created.
4. **Save**.

You can reuse the **same credential** on as many sources as you like (for example, one
token that can read several private repos). Leave **Credential** empty to fall back to the
global `GITHUB_TOKEN` environment variable.

---

## 5. Sync the source

After attaching the credential:

1. Run the admin action **Sync documentation**, or from a shell:

   ```bash
   python manage.py sync_docs
   ```

2. Run **Import navigation structure from provider** if the site has no navigation yet.
3. Open the site and confirm its pages, navigation, and assets load.

Check **last sync status** and **last sync error** on the source if anything fails.

---

## 6. Token resolution order

When the app calls GitHub it uses the first token available:

1. The **Credential** attached to the source (if set and non-empty).
2. The **`GITHUB_TOKEN`** environment variable (fallback for sources without a credential).

Set `GITHUB_TOKEN` for a single-token setup, for example:

```bash
GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**Recommendation:** use stored credentials for per-repo or shared access, and keep
`GITHUB_TOKEN` only as a fallback.

---

## 7. Security and storage

- Tokens are **encrypted at rest** before they are written to the database.
- The encryption key is derived from `DJANGO_SECRET_KEY`. **Keep that key stable** — if it
  changes, the stored tokens can no longer be decrypted and private syncs fail until you
  re-enter each token.
- Never put a token in a template, log, error message, or commit. `.env` is git-ignored;
  keep it that way.
- Grant the narrowest access possible: read-only `Contents` for fine-grained tokens, or
  the `repo` scope for classic tokens.
- Revoke a token in GitHub if it leaks, then replace it in the credential record (edit the
  credential and paste the new token).

---

## 8. Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| Sync fails with `401` / `403` | Token is invalid, expired, revoked, or lacks permission for that repo. Regenerate the PAT and re-enter it in the credential. |
| Sync fails with `404` | Wrong `owner`/`repository`, wrong `branch`, or the token cannot see the private repo. Verify the repo coordinates and the token's repo access. |
| Private docs worked, then stopped | `DJANGO_SECRET_KEY` changed (tokens can no longer be decrypted) or the token was revoked. Re-enter the token. |
| Public repo syncs but private does not | The source has no **Credential** selected and no valid `GITHUB_TOKEN`. Attach a credential. |
| Credential dropdown is empty | No credentials exist yet — create one under **GitHub credentials → Add**. |

---

## GitHub sign-in vs. docs access

These are two independent features:

| Purpose | What to configure |
| --- | --- |
| Sign in to the app **with GitHub** (SSO) | `GITHUB_CLIENT_ID` and `GITHUB_SECRET` (a GitHub OAuth App). |
| Read **private repos** for documentation | A `GitHubCredential` (PAT), or `GITHUB_TOKEN`. |

The tutorial above covers the second one. For SSO, create a GitHub OAuth App and set the
client ID/secret environment variables, then run `python manage.py setup_social_apps`.
