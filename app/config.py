import os
import secrets

_DEFAULT_INSECURE_SECRET_KEY = "dev-insecure-key-change-me"


def _str_to_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    """Application configuration, populated from environment variables.

    Values are read in __init__ (not as class-body attributes) so that each
    create_app() call picks up current environment variables. Class-body
    attributes would only be evaluated once at first import, which silently
    ignores env changes made afterwards (e.g. monkeypatch.setenv in tests,
    or .env reloads).
    """

    def __init__(self):
        self.DEBUG = _str_to_bool(os.getenv("FLASK_DEBUG", "0"))

        secret_key = os.getenv("SECRET_KEY", "")
        if not secret_key or secret_key == _DEFAULT_INSECURE_SECRET_KEY:
            if self.DEBUG:
                # Convenient for local development only: an ephemeral random
                # key means sessions won't survive a restart, which is a
                # loud, obvious signal (nobody stays logged in) rather than a
                # silent, exploitable default shared by every deployment.
                secret_key = secrets.token_hex(32)
            else:
                raise RuntimeError(
                    "SECRET_KEY is not set (or is still the insecure default). "
                    "Set a unique, random SECRET_KEY in your environment/.env "
                    "before running outside of FLASK_DEBUG=1. Generate one with: "
                    'python -c "import secrets; print(secrets.token_hex(32))"'
                )
        self.SECRET_KEY = secret_key

        self.DATABASE_PATH = os.getenv("DATABASE_PATH", "lego_sets.db")
        self.SETS_DIR = os.getenv("SETS_DIR", "sets")

        self.BRICKSET_API_KEY = os.getenv("BRICKSET_API_KEY")
        self.BRICKSET_USERNAME = os.getenv("BRICKSET_USERNAME")
        self.BRICKSET_PASSWORD = os.getenv("BRICKSET_PASSWORD")

        self.SETS_PER_PAGE = int(os.getenv("SETS_PER_PAGE", "10"))
        self.MAX_CONTENT_LENGTH = int(
            os.getenv("MAX_CONTENT_LENGTH", str(25 * 1024 * 1024))
        )
        self.MAX_DOWNLOAD_BYTES = int(
            os.getenv("MAX_DOWNLOAD_BYTES", str(25 * 1024 * 1024))
        )

        # Cookie/session hardening — see README "Security" section. The app
        # itself can't detect whether a reverse proxy is terminating HTTPS in
        # front of it, so SESSION_COOKIE_SECURE defaults to off (so a plain
        # local/LAN HTTP deployment still works) — but it MUST be set to "1"
        # once this is deployed behind HTTPS, or the session cookie can be
        # intercepted in transit.
        self.SESSION_COOKIE_SECURE = _str_to_bool(
            os.getenv("SESSION_COOKIE_SECURE", "0")
        )
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = "Lax"
