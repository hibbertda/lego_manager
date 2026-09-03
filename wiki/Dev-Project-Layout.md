# Dev: Project Layout

```
app/                Flask application factory, services, config + blueprints
  auth_ops.py           SQLite data access layer (users, OIDC provider config)
  brickset_ops.py       Brickset API client (with retries/timeouts)
  sql_ops.py            SQLite data access layer (sets)
  decorators.py         @admin_required view decorator
  oidc.py               Runtime-configurable Authlib OIDC client wrapper
  user.py               Flask-Login User wrapper
  blueprints/main.py    "/" redirects to My Sets (the default landing page)
  blueprints/sets.py    add/list/search/detail routes + safe static file serving
  blueprints/auth.py    /login, /logout, /setup, OIDC login/callback
  blueprints/admin.py   /admin/users, /admin/sso, /admin/brickset — server settings UI
templates/          Jinja templates (Bootstrap 5, locally compiled — see static/)
cli.py              `python cli.py add-set <number>` for scripted imports
wsgi.py             Dev server entrypoint / gunicorn target
tests/              pytest suite (DB layer + route + auth smoke tests)
static/src/custom-bootstrap.scss   Sass entry point: Bootstrap variable overrides
                    (LEGO color palette, system fonts) + custom component styles
static/css/app.css     Compiled, self-hosted stylesheet served to the browser
static/js/app.js       Delegated event handlers for CSP-safe interactivity
                    (confirmation popovers, auto-submit selects, etc.)
static/js/pdf-viewer.js  Custom instructions PDF viewer built on PDF.js
static/js/bootstrap.bundle.min.js  Bootstrap's JS bundle (copied locally, no CDN)
```

See [Dev-Frontend-Build](Dev-Frontend-Build.md) for how everything under
`static/` gets built, and [Security](Security.md) for why interactivity
lives in `app.js` rather than inline HTML attributes.
