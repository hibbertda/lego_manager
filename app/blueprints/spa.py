"""Serves the built React SPA (frontend/ -> static/app/ via `npm run build`)
under /app/*, entirely separate from the legacy Jinja-rendered routes in
sets.py/admin.py/utility.py/auth.py, which continue to work unchanged at
their existing URLs. This blueprint is purely additive: it doesn't touch any
existing route, template, or static asset.

Client-side routing (react-router) means every /app/<anything> path must
serve the same index.html and let the browser's JS take over routing; only
actual static asset requests (js/css/images under /app/assets/...) should
hit disk directly, which Flask's static handler for the 'app' folder already
covers via send_from_directory below.
"""

import os

from flask import Blueprint, current_app, send_from_directory

spa_bp = Blueprint("spa", __name__, url_prefix="/app")


def _spa_dir() -> str:
    return os.path.join(current_app.static_folder, "app")


@spa_bp.route("/")
@spa_bp.route("/<path:subpath>")
def index(subpath: str | None = None):
    spa_dir = _spa_dir()
    # If the path matches a real built asset (e.g. /app/assets/index-abc123.js),
    # serve it directly; otherwise fall back to index.html so react-router can
    # render the matching client-side route (standard SPA history-mode setup).
    if subpath:
        candidate = os.path.join(spa_dir, subpath)
        if os.path.isfile(candidate):
            return send_from_directory(spa_dir, subpath)

    index_path = os.path.join(spa_dir, "index.html")
    if not os.path.isfile(index_path):
        return (
            "React SPA build not found. Run `npm install && npm run build` "
            "inside frontend/ first (see frontend/README.md).",
            404,
        )
    return send_from_directory(spa_dir, "index.html")
