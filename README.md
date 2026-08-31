# LEGO Manager

A personal web app for tracking the LEGO sets you own. Add a set by number and it
pulls set details and images from [Brickset](https://brickset.com/api/v3.asmx),
plus the official building-instructions PDF directly from LEGO.com, so you can
browse your collection and re-view any set's instructions from the browser.

## Features

- Add a set by number — fetches metadata, box art, and the official instructions PDF
- Add a set manually (name, year, theme, pieces, optional image/PDF upload) when
  Brickset isn't available, isn't configured, or you'd simply rather not use it
- Browse your collection with pagination, list/grid views, and a theme filter sidebar
- Search sets by name, with a predictive live-search box in the top bar
- View a set's detail page with images and an embedded PDF viewer for instructions
- Track build progress (page + status) per set so you can pick up a build later
- Remove a set (admin only)
- Authentication: local accounts by default, with optional OIDC single sign-on
  (e.g. Authentik). Admins can manage users/roles and SSO config from the UI.
- CLI for bulk/scripted imports without the web UI

## Project layout

```
app/                Flask application factory + config + blueprints
  decorators.py         @admin_required view decorator
  oidc.py               Runtime-configurable Authlib OIDC client wrapper
  user.py               Flask-Login User wrapper
  blueprints/main.py    "/" redirects to My Sets (the default landing page)
  blueprints/sets.py    add/list/search/detail routes + safe static file serving
  blueprints/auth.py    /login, /logout, /setup, OIDC login/callback
  blueprints/admin.py   /admin/users, /admin/sso, /admin/brickset — server settings UI
templates/          Jinja templates (Bootstrap 5, locally compiled — see static/)
sql_ops.py          SQLite data access layer (sets)
auth_ops.py         SQLite data access layer (users, OIDC provider config)
brickset_ops.py      Brickset API client (with retries/timeouts)
cli.py              `python cli.py add-set <number>` for scripted imports
wsgi.py             Dev server entrypoint / gunicorn target
tests/              pytest suite (DB layer + route + auth smoke tests)
static/src/custom-bootstrap.scss   Sass entry point: Bootstrap variable overrides
                    (LEGO color palette, system fonts) + custom component styles
static/css/app.css     Compiled, self-hosted stylesheet served to the browser
static/js/bootstrap.bundle.min.js  Bootstrap's JS bundle (copied locally, no CDN)
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # then set a SECRET_KEY (Brickset API key is optional here — see below)
```

Generate a `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Building the CSS/JS

The UI is built on Bootstrap 5, compiled ahead of time from Sass and served as
a plain, same-origin static file — no CDN or external font requests are made
by the browser at runtime. Run this once after cloning (and again any time you
change `static/src/custom-bootstrap.scss` or template markup):

```bash
npm install
npm run build
```

This generates `static/css/app.css` (compiled Sass, including Bootstrap +
custom theme) and `static/js/bootstrap.bundle.min.js` (copied from
`node_modules`), which `base.html` links to directly. Node is only needed for
this build step — it is not required to run the app.

## Running (development)

```bash
source .venv/bin/activate
python wsgi.py
```

Visit http://127.0.0.1:5000 — on first run you'll be redirected to `/setup` to
create the initial admin account.

## Authentication

- **Local accounts**: the first visit to the app redirects to `/setup` to create
  an admin account (username + password, hashed with Werkzeug's
  `generate_password_hash`). After that, all pages require login.
- **Roles**: `admin` can manage users/SSO config and delete sets. `user` can add
  and view sets (including everyone's build status) but cannot delete sets or
  reach the admin area.
- **Admin UI**: logged-in admins see an "Admin" link (in the user menu) leading
  to a sidebar with sections for user management, SSO configuration, and
  Brickset API settings.
- **OIDC / SSO**: configure a generic OIDC provider (e.g. Authentik) entirely
  from `/admin/sso` — no env vars needed. Provide the issuer URL (its
  `/.well-known/openid-configuration` must be reachable), client ID/secret,
  scopes, and a default role for newly-created SSO users, then enable it. A
  "Sign in with <provider>" link appears on the login page once enabled.
  OIDC users are matched/created by their `sub` claim.
- **Hiding local login**: once SSO is enabled, admins can check "Hide local
  login form on the main login page" to remove the username/password form
  from `/login` (only the SSO button is shown). Local login is never fully
  removed, though — it always remains reachable as a break-glass fallback at
  `/login/local`, so you can still get in with a local account if the
  external IdP has an outage.

## Brickset API settings

The Brickset API key (and optional username/password, used only for
owned/wanted collection sync features this app doesn't currently exercise)
can be configured from `/admin/brickset` in the UI — no server restart or
`.env` edit required. `BRICKSET_API_KEY` in `.env`/the environment still
works as a bootstrap/fallback value: it's only used when nothing has been
saved in the database yet, and is overridden the moment an admin saves a key
from the UI.

## Running (production-like, via gunicorn)

```bash
gunicorn -b 0.0.0.0:8000 --workers 2 wsgi:app
```

## Running with Docker

Build and run locally from source:

```bash
docker compose up --build
```

Or pull the pre-built image published by CI (see below) instead of building
locally — useful on the actual deployment host:

```bash
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
```

## CI: building and publishing the image

`.gitea/workflows/build-image.yml` builds the Docker image on the in-cluster
Gitea Actions runner and pushes it to the Gitea container registry as
`gitea.thehibbs.net/xamlok/lego_manager`, tagged both `latest` (or a
manually-chosen tag) and the short commit SHA. It runs automatically on every
push to `main`, or on demand via Actions -> "Build lego-manager image" -> "Run
workflow".

One-time setup required in the Gitea repo:
- Generate a Personal Access Token (Settings -> Applications) with
  `write:package` and `read:package` scopes — the built-in Actions token
  doesn't have registry write access.
- Add it as a repo secret named `DOCKERBUILD_SECRET` (Repo -> Settings -> Actions
  -> Secrets).

After a new image is pushed, running deployments need to be restarted to pull
it (mutable tags aren't automatically re-pulled):

```bash
# Kubernetes
kubectl -n lego-manager rollout restart deploy/lego-manager

# docker compose
docker compose pull && docker compose up -d
```

## CLI usage

```bash
python cli.py add-set 75386
```

## Tests

```bash
pytest -q
```

## Security notes

- Never commit `.env` — it holds your Brickset API key and app `SECRET_KEY`.
- `FLASK_DEBUG` must stay `0`/unset outside local development.
- `SECRET_KEY` is required in `.env`/the environment and must not be left as
  the documented insecure default; the app fails fast at startup if it's
  missing or still set to that default, except when `FLASK_DEBUG=1`, where
  an ephemeral random key is generated instead (sessions won't persist across
  dev-server restarts in that mode — a deliberate, visible tradeoff for local
  development only).
- Set `SESSION_COOKIE_SECURE=1` once the app is served over HTTPS (directly
  or via a reverse proxy that terminates TLS). It defaults to off so plain
  local/LAN HTTP development keeps working; it is **not** auto-detected.
- CSRF protection is enabled (Flask-WTF) on all POST forms.
- Login (`/login`, `/login/local`) is rate-limited (10 attempts/minute per
  IP) and the OIDC callback is rate-limited (20/minute per IP) to slow down
  brute-force/credential-stuffing attempts. This uses Flask-Limiter's default
  in-memory storage, which is **not shared across worker processes** — with
  the default `gunicorn --workers 2` in the provided `Dockerfile`, the
  effective limit is roughly double the configured value. For a stronger
  guarantee (or if you scale beyond a couple of workers), configure a shared
  backend such as Redis via `Limiter(storage_uri=...)`.
- Responses include baseline security headers (`X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY`, a restrictive `Content-Security-Policy`
  with no CDN/inline-script exceptions, and `Referrer-Policy: same-origin`).
  `Strict-Transport-Security` is intentionally not set by the app itself —
  add it at your reverse proxy once you're serving over HTTPS.
- Manually-uploaded images and PDFs (via "Add a Set" → Manual) are validated
  by actual file content (Pillow image decode / PDF magic bytes), not just
  by filename extension, to reduce the risk of spoofed/malicious uploads.
- Static file serving under `/sets/<path>` is guarded against path traversal.
- All pages require authentication (local or OIDC); the last remaining admin
  account cannot be demoted, deactivated, or deleted through the UI.
- OIDC client secrets are stored in `lego_sets.db` (not env vars) so they can
  be managed from the UI — back up/secure the database file accordingly.
- The provided `Dockerfile` runs the app as a dedicated non-root `appuser`
  rather than root. If you bind-mount `lego_sets.db`/`sets/` from the host
  (as `docker-compose.yml` does), ensure those paths are writable by that
  user (e.g. `chmod`/`chown` on the host, or align UIDs) or the container
  will fail to write to them.
