# Installation

The supported way to run LEGO Manager is Docker Compose. See
[Development](Development.md) instead if you want to run the app from source
for local development.

## 1. Get the files

Clone the repo, or just copy `docker-compose.yml` (or
`docker-compose.registry.yml`) and `.env.example` from it.

## 2. Configure environment variables

```bash
cp .env.example .env
```

At minimum, set a `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

See [Configuration](Configuration.md) for what every variable does — most are
optional and have sane defaults.

## 3. Run it

**Option A — build the image locally from source:**

```bash
docker compose up --build
```

**Option B — pull the pre-built image** published by CI to the Gitea
container registry (useful on the actual deployment host, so it doesn't need
a full source checkout or a Docker build toolchain):

```bash
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
```

Either way, the container stores its SQLite database in `./data/` and set
images/instruction PDFs in `./sets/`, both bind-mounted from the current
directory so they persist across container restarts/upgrades.

## 4. First run

Visit `http://<host>:8000` — you'll be redirected to `/setup` to create the
initial admin account. After that, all pages require login. See
[Configuration](Configuration.md) for roles, OIDC/SSO, and the Brickset API
key.

## Upgrading an existing deployment

Pull the new image and recreate the container:

```bash
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
```

> **Upgrading from a very old deployment?** Early versions bind-mounted
> `./lego_sets.db` directly as a file instead of a `data/` directory. If you
> have one of those, move it into `data/` before restarting so the app finds
> your existing sets instead of creating a fresh empty database:
> ```bash
> mkdir -p data && mv lego_sets.db data/lego_sets.db
> ```

## Running without Docker (production-like)

```bash
pip install -r requirements.txt
gunicorn -b 0.0.0.0:8000 --workers 2 --threads 4 --worker-class gthread --timeout 60 wsgi:app
```

This still needs the pre-built frontend assets (`static/css/app.css`,
`static/js/bootstrap.bundle.min.js`, `static/js/pdfjs/`) to already be
present — see [Dev-Frontend-Build](Dev-Frontend-Build.md) if you're building
from a fresh source checkout rather than a release/image that already
includes them.
