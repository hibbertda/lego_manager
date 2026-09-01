# LEGO Manager

A personal web app for tracking the LEGO sets you own. Add a set by number
and it pulls set details and box art from
[Brickset](https://brickset.com/api/v3.asmx), plus the official
building-instructions PDF directly from LEGO.com, so you can browse your
collection and re-view any set's instructions from the browser.

## Features

- Add a set by number — fetches metadata, box art, and the official
  instructions PDF automatically
- Add a set manually (name, year, theme, pieces, optional image/PDF upload)
  when Brickset isn't available, isn't configured, or you'd simply rather
  not use it
- Browse your collection with pagination, list/grid views (grid is the
  default, styled after LEGO.com's shop cards), and sidebar filters for
  favorites, theme, and build status (Not Started / In Progress / Complete /
  Storage)
- Mark sets as favorites with one click (heart icon), and filter down to
  just your favorites from the sidebar
- Change a set's build status directly from its list/grid card via a quick
  dropdown, without opening the set detail page
- Search sets by name, with a predictive live-search box in the top bar
- View a set's detail page with images and a self-hosted PDF.js viewer for
  instructions — auto-saves your reading progress as you browse, supports
  switching between multiple instruction booklets, and can be resized by
  dragging its bottom edge
- Track build progress (page + status) per set so you can pick up a build
  later
- Remove a set (admin only), with a confirmation prompt before deleting
- Authentication: local accounts by default, with optional OIDC single
  sign-on (e.g. Authentik). Admins can manage users/roles and SSO config
  from the UI.
- CLI for bulk/scripted imports without the web UI

## Quick start

The supported way to run LEGO Manager is Docker Compose:

```bash
cp .env.example .env   # then set a SECRET_KEY (see docs below)
docker compose up --build
```

Visit `http://localhost:8000` — you'll be redirected to `/setup` to create
the initial admin account.

## Documentation

Full documentation lives in the project [Wiki](wiki/Home.md) (also mirrored
locally under [`wiki/`](wiki/) in this repo):

- [Installation](wiki/Installation.md) — Docker Compose setup, upgrading
- [Configuration](wiki/Configuration.md) — environment variables, Brickset
  API, authentication & SSO
- [Security](wiki/Security.md) — security posture and hardening notes
- [Development](wiki/Development.md) — running from source, project layout,
  frontend build, testing, CI/CD

## Tests

```bash
pytest -q
```

## License

[MIT](LICENSE)
