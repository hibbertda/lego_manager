import logging
import os

from dotenv import load_dotenv

# Load .env before Config (imported below) evaluates any os.getenv() defaults,
# otherwise values from .env would be ignored on first import.
load_dotenv()

from flask import Flask, redirect, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user
from flask_wtf import CSRFProtect

from app.auth_ops import AuthOps
from app.brickset_ops import BricksetAPI
from app.config import Config
from app.oidc import OIDCManager
from app.sql_ops import DatabaseOps

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
# Brute-force protection for login/OIDC-callback endpoints (applied per-route
# in app/blueprints/auth.py). In-memory storage is fine for this app's single
# small-deployment threat model; if you scale to multiple worker processes
# behind a shared storage backend (e.g. Redis), point storage_uri there
# instead so limits are enforced consistently across workers.
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def _resolve_path(path: str) -> str:
    """Resolve a possibly-relative config path against the project root, not
    Flask's app.root_path (which points at the app/ package, not the project)."""
    return path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)


def create_app(config_class: type = Config) -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )
    app.config.from_object(config_class())
    app.config["DATABASE_PATH"] = _resolve_path(app.config["DATABASE_PATH"])
    app.config["SETS_DIR"] = _resolve_path(app.config["SETS_DIR"])

    logging.basicConfig(level=logging.DEBUG if app.config["DEBUG"] else logging.INFO)

    csrf.init_app(app)
    limiter.init_app(app)

    app.db_ops = DatabaseOps(app.config["DATABASE_PATH"])
    app.auth_ops = AuthOps(app.config["DATABASE_PATH"])

    # Brickset API credentials can be configured from the admin UI; the DB
    # value (if set) takes precedence over the .env-sourced Config default,
    # which acts as a fallback/initial-bootstrap value only.
    brickset_settings = app.db_ops.get_brickset_settings()
    api_key = (brickset_settings or {}).get("api_key") or app.config["BRICKSET_API_KEY"]
    app.brickset_api = BricksetAPI(api_key)

    login_manager.init_app(app)
    app.oidc_oauth = OIDCManager(app)

    @app.after_request
    def _set_security_headers(response):
        # Baseline hardening headers for all responses. CSP is scoped to this
        # app's actual asset usage: all JS/CSS/fonts are self-hosted (no CDNs),
        # so script-src can stay strict with no 'unsafe-inline'. style-src allows
        # 'unsafe-inline' only because several templates use inline style="..."
        # attributes for one-off sizing — inline *scripts* (the actual XSS
        # vector) are never allowed. HSTS is left to the reverse proxy/operator
        # since this app doesn't know whether it's served over HTTPS.
        #
        # Framing is restricted to same-origin (not fully denied): earlier this
        # mattered for the browser's native <embed type="application/pdf">
        # viewer; now instructions render via a self-hosted PDF.js canvas
        # viewer instead, but same-origin framing is still kept as a sane
        # default that doesn't affect legitimate use while blocking third-party
        # clickjacking.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; frame-ancestors 'self'; base-uri 'self'; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            # 'wasm-unsafe-eval' (not full 'unsafe-eval') is required by
            # PDF.js, which compiles WebAssembly modules for certain image/font
            # codecs (e.g. JPX/JBIG2) used in instruction PDFs.
            "script-src 'self' 'wasm-unsafe-eval'; font-src 'self'",
        )
        return response

    @app.context_processor
    def _inject_add_set_globals():
        # Used by the global "Add a Set" modal (embedded in base.html on every
        # authenticated page), so it needs to be available everywhere, not
        # just on a single route's render_template call.
        if not current_user.is_authenticated:
            return {}
        return {"brickset_configured": bool(app.brickset_api.api_key)}

    @app.context_processor
    def _inject_build_status_meta():
        # Single source of truth for build_status display (badge color/icon,
        # dropdown labels, sidebar status filter) — see BUILD_STATUS_META in
        # sql_ops.py. Exposed globally so templates don't each redefine it.
        from app.sql_ops import BUILD_STATUS_META, VALID_BUILD_STATUSES

        return {
            "build_statuses": VALID_BUILD_STATUSES,
            "status_labels": {k: v["label"] for k, v in BUILD_STATUS_META.items()},
            "status_icons": {k: v["icon"] for k, v in BUILD_STATUS_META.items()},
            "status_badge_classes": {
                k: v["badge_class"] for k, v in BUILD_STATUS_META.items()
            },
        }

    @login_manager.user_loader
    def load_user(user_id):
        from app.user import User

        data = app.auth_ops.get_user_by_id(int(user_id))
        return User(data) if data and data.get("is_active", True) else None

    @app.before_request
    def _require_login():
        # Endpoints reachable without an authenticated session.
        open_endpoints = {
            "auth.login",
            "auth.setup",
            "auth.oidc_login",
            "auth.oidc_callback",
            "auth.local_login",
            "static",
        }
        endpoint = request.endpoint
        if endpoint is None or endpoint in open_endpoints:
            return None

        if not app.auth_ops.has_any_users():
            return redirect(url_for("auth.setup"))

        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        return None

    from app.blueprints.admin import admin_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.main import main_bp
    from app.blueprints.sets import sets_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(sets_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    return app
