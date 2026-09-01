# Development

Hub page for everything related to developing/contributing to LEGO Manager.
See [Home](Home.md) for the user/operator-facing pages instead.

- **[Dev-Environment-Setup](Dev-Environment-Setup.md)** — venv, installing
  deps, building frontend assets, running the dev server
- **[Dev-Project-Layout](Dev-Project-Layout.md)** — a tour of the codebase:
  directories, blueprints, and the data-access layer
- **[Dev-Frontend-Build](Dev-Frontend-Build.md)** — the Sass/Bootstrap build
  pipeline and the self-hosted PDF.js instructions viewer
- **[Dev-Testing](Dev-Testing.md)** — running the pytest suite
- **[Dev-CI-CD](Dev-CI-CD.md)** — the Gitea Actions workflow that builds and
  publishes the Docker image

## Quick reference

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
npm install && npm run build
cp .env.example .env   # then set a SECRET_KEY
python wsgi.py         # http://127.0.0.1:5000
pytest -q
```
