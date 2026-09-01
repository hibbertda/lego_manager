# Configuration

## Environment variables (`.env`)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `SECRET_KEY` | Yes (unless `FLASK_DEBUG=1`) | *(insecure placeholder)* | Signs session cookies and CSRF tokens. The app refuses to start if this is missing or left as the documented insecure default, except under `FLASK_DEBUG=1`, where an ephemeral random key is generated instead (sessions won't persist across dev-server restarts in that mode). Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `FLASK_DEBUG` | No | `0` | Set to `1` only for local development. **Never enable in production.** |
| `SESSION_COOKIE_SECURE` | No | `0` | Set to `1` once the app is served over HTTPS (directly or via a reverse proxy terminating TLS), so the session cookie is marked `Secure`. Not auto-detected. |
| `DATABASE_PATH` | No | `lego_sets.db` | Path to the SQLite database file. The provided `docker-compose.yml` points this at a mounted `data/` directory. |
| `BRICKSET_API_KEY` | No | *(none)* | Bootstrap/fallback Brickset API key — only used until an admin saves a key from the UI (see below), which then takes precedence. |

Authentication (local accounts, roles, OIDC/SSO) is **not** configured via
environment variables — it's all managed at runtime from the admin UI, so it
can be changed without a restart or redeploy. See below.

## Brickset API

[Brickset](https://brickset.com/tools/webservices/requestkey) provides the
set metadata, box art, and instructions lookup used by "Add a Set" ->
Automatic. Configure the API key (and optional username/password, used only
for owned/wanted collection sync features this app doesn't currently
exercise) from `/admin/brickset` in the UI — no server restart or `.env` edit
required.

If you'd rather not use Brickset at all, use "Add a Set" -> Manual instead
(name, year, theme, pieces, optional image/PDF upload).

## Authentication

- **Local accounts**: the first visit to the app redirects to `/setup` to
  create an admin account (username + password, hashed with Werkzeug's
  `generate_password_hash`). After that, all pages require login.
- **Roles**: `admin` can manage users/SSO config and delete sets. `user` can
  add and view sets (including everyone's build status) but cannot delete
  sets or reach the admin area. The last remaining admin account cannot be
  demoted, deactivated, or deleted through the UI.
- **Admin UI**: logged-in admins see an "Admin" link (in the user menu)
  leading to a sidebar with sections for user management, SSO configuration,
  and Brickset API settings.

### OIDC / Single sign-on

Configure a generic OIDC provider (e.g. [Authentik](https://goauthentik.io/))
entirely from `/admin/sso` — no env vars needed:

1. Provide the issuer URL (its `/.well-known/openid-configuration` must be
   reachable from the app), client ID/secret, scopes, and a default role for
   newly-created SSO users.
2. Enable it. A "Sign in with `<provider>`" link then appears on the login
   page.

OIDC users are matched/created by their `sub` claim. Client secrets are
stored in the app database (not env vars) so they can be managed from the UI
— back up/secure the database file accordingly.

**Hiding local login:** once SSO is enabled, admins can check "Hide local
login form on the main login page" to remove the username/password form from
`/login` (only the SSO button is shown). Local login is never fully removed
though — it always remains reachable as a break-glass fallback at
`/login/local`, so you can still get in with a local account if the external
IdP has an outage.

## CLI

Bulk/scripted imports without the web UI:

```bash
python cli.py add-set 75386
```
