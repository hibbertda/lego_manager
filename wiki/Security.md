# Security notes

Operational security posture for anyone deploying LEGO Manager.

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
- `TRUST_PROXY_HEADERS` defaults to `1` (the app trusts one hop of
  `X-Forwarded-Proto`/`Host`/`Port` from whatever's in front of it via
  Werkzeug's `ProxyFix`), since this app is expected to always run behind a
  reverse proxy. Only set it to `0` if gunicorn is ever exposed directly to
  clients with no proxy in front — trusting these headers from an untrusted
  client would let them spoof scheme/host. Leaving it off behind a proxy
  (or having a proxy that doesn't set these headers) is the most common
  cause of OIDC login failing with a redirect_uri/scheme mismatch, since
  `url_for(..., _external=True)` would otherwise build the callback URL
  using the proxy's plain-HTTP connection to the app instead of the
  public HTTPS one.
- CSRF protection is enabled (Flask-WTF) on all POST forms.
- Login (`/login`, `/login/local`) is rate-limited (10 attempts/minute per
  IP) and the OIDC callback is rate-limited (20/minute per IP) to slow down
  brute-force/credential-stuffing attempts. This uses Flask-Limiter's default
  in-memory storage, which is **not shared across worker processes** — with
  the default `gunicorn --workers 2 --threads 4` in the provided
  `Dockerfile`, the effective limit is roughly double the configured value
  (in-memory storage is per-*process*, so it's shared across the threads
  within a worker but not across the 2 worker processes). For a stronger
  guarantee (or if you scale beyond a couple of workers), configure a shared
  backend such as Redis via `Limiter(storage_uri=...)`.
- Responses include baseline security headers (`X-Content-Type-Options:
  nosniff`, `X-Frame-Options: SAMEORIGIN`, a restrictive
  `Content-Security-Policy` with no CDN/inline-script exceptions, and
  `Referrer-Policy: same-origin`). Framing is same-origin rather than fully
  denied because the instructions viewer needs it; this still fully blocks
  third-party clickjacking, the actual risk these headers exist for.
  `Strict-Transport-Security` is intentionally not set by the app itself —
  add it at your reverse proxy once you're serving over HTTPS.
- Because the CSP has no `unsafe-inline` exception, all interactive UI
  behavior must go through external scripts (`static/js/app.js`) with
  delegated event listeners — inline `onclick`/`onchange`/`onsubmit`
  attributes are silently blocked by the browser. Keep this in mind if you
  add new templates (see [Dev-Frontend-Build](Dev-Frontend-Build.md)).
- Manually-uploaded images and PDFs (via "Add a Set" -> Manual) are validated
  by actual file content (Pillow image decode / PDF magic bytes), not just
  by filename extension, to reduce the risk of spoofed/malicious uploads.
- Static file serving under `/sets/<path>` is guarded against path
  traversal.
- All pages require authentication (local or OIDC); the last remaining admin
  account cannot be demoted, deactivated, or deleted through the UI.
- OIDC client secrets are stored in `lego_sets.db` (not env vars) so they can
  be managed from the UI — back up/secure the database file accordingly.
- The provided `Dockerfile` runs the app as a dedicated non-root `appuser`
  rather than root. `docker-entrypoint.sh` starts as root just long enough to
  fix ownership of the bind-mounted `data/`/`sets/` directories, then drops
  to `appuser` (via `gosu`) before running gunicorn — no manual `chown` on
  the host is required. `docker-compose.yml` mounts a `data/` *directory*
  (containing `lego_sets.db`) rather than bind-mounting the `.db` file
  directly, since Docker silently creates a directory instead of a file at a
  bind-mount target that doesn't already exist on the host — mounting a
  directory sidesteps that footgun entirely.
