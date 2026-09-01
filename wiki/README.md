# LEGO Manager Wiki (source)

This folder is the **source of truth** for the project's Gitea wiki. Gitea
wikis live in a separate git repository (`lego_manager.wiki.git`), so these
pages aren't rendered automatically just by living in this folder — they need
to be copied/pushed into that wiki repo whenever they change.

## Publishing these pages to the actual wiki

```bash
# One-time clone of the wiki repo (a sibling to the main repo)
git clone https://gitea.thehibbs.net/xamlok/lego_manager.wiki.git ../lego_manager.wiki

# Whenever wiki/ changes here, copy the updated pages over and push
cp wiki/*.md ../lego_manager.wiki/
cd ../lego_manager.wiki
git add -A
git commit -m "Sync wiki from main repo"
git push
```

Gitea creates the wiki repo automatically the first time a wiki page is saved
through its web UI, or the first time something is pushed to
`<repo>.wiki.git` — if the clone above fails because the repo doesn't exist
yet, create the first page from the web UI (Wiki tab -> "Create the first
page") and then `git clone` will work.

## Page index

Gitea wikis are a flat namespace (no real folders), so related pages are
grouped by filename prefix and cross-linked instead. Two entry points:

- **[Home](Home.md)** — project overview and links to everything else
- **[Development](Development.md)** — hub page for everything related to
  developing/contributing to the project (the `Dev-*` pages)

| Page | Purpose |
|---|---|
| `Home.md` | Wiki landing page |
| `Installation.md` | Installing/running the app (Docker Compose, upgrading) |
| `Configuration.md` | Environment variables, Brickset API, authentication & SSO setup |
| `Security.md` | Security posture and hardening notes for operators |
| `Development.md` | Hub/index page for the Dev section |
| `Dev-Environment-Setup.md` | Local dev environment (venv, npm build, dev server) |
| `Dev-Project-Layout.md` | Codebase tour: directories, modules, data layer |
| `Dev-Frontend-Build.md` | Sass/Bootstrap build pipeline and the PDF.js viewer |
| `Dev-Testing.md` | Running the test suite |
| `Dev-CI-CD.md` | Gitea Actions image build/publish workflow |
