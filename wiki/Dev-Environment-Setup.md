# Dev: Environment Setup

## Prerequisites

- Python 3 with `venv`
- Node.js/npm (only needed for the one-time/occasional frontend asset build
  — not required to run the app itself)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # then set a SECRET_KEY (Brickset API key is optional — see Configuration)
```

Generate a `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Build the frontend assets (see [Dev-Frontend-Build](Dev-Frontend-Build.md)
for details on what this generates and when to re-run it):

```bash
npm install
npm run build
```

## Running the dev server

```bash
source .venv/bin/activate
python wsgi.py
```

Visit `http://127.0.0.1:5000` — on first run you'll be redirected to
`/setup` to create the initial admin account.

> **Note:** with `FLASK_DEBUG=0` (the default, and required outside local
> development — see [Security](Security.md)), Flask's auto-reloader and
> Jinja template caching behave differently than a typical dev setup: Python
> and template changes are **not** picked up automatically. Restart
> `python wsgi.py` after editing any `.py` or `templates/*.html` file. CSS/JS
> changes under `static/` do not require a restart, just a browser refresh
> (and `npm run build:css`/`build:js` if you edited the Sass/JS sources
> rather than the compiled output directly).

## Production-like run (gunicorn)

```bash
gunicorn -b 0.0.0.0:8000 --workers 2 wsgi:app
```
