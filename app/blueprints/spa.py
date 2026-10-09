"""Serves the built React SPA (frontend/ -> static/app/ via `npm run build`)
at the site root. This is the only UI left in the app — the legacy
Jinja-rendered pages (set list, wishlist, search, admin, utility, etc.) have
been removed; only a few genuinely load-bearing non-UI routes remain in
sets.py (image/instruction/label file-serving) and auth.py (the OIDC
redirect dance), which the React app/API layer still depends on directly.

Client-side routing (react-router) means every path not matching one of
those routes must serve the same index.html and let the browser's JS take
over routing; only actual static asset requests (js/css/images under
/assets/...) should hit disk directly, which Flask's static handler for the
'app' folder already covers via send_from_directory below.
"""

import os

from flask import Blueprint, current_app, send_from_directory

spa_bp = Blueprint("spa", __name__)


def _spa_dir() -> str:
    return os.path.join(current_app.static_folder, "app")


@spa_bp.route("/")
@spa_bp.route("/<path:subpath>")
def index(subpath: str | None = None):
    spa_dir = _spa_dir()
    # If the path matches a real built asset (e.g. /assets/index-abc123.js),
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
