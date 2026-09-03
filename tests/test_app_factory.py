from flask import url_for


def _register_echo_route(flask_app):
    """Test-only route that reports what url_for(_external=True) resolves
    to for the OIDC callback, so we can verify ProxyFix rewrites the
    scheme/host from X-Forwarded-* headers when TRUST_PROXY_HEADERS is on."""

    @flask_app.route("/__test/echo-oidc-redirect-uri")
    def _echo():
        return url_for("auth.oidc_callback", _external=True)


def _make_app(tmp_path, monkeypatch, trust_proxy_headers=None):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test_lego.db"))
    monkeypatch.setenv("SETS_DIR", str(tmp_path / "sets"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("BRICKSET_API_KEY", "test-key")
    if trust_proxy_headers is not None:
        monkeypatch.setenv("TRUST_PROXY_HEADERS", trust_proxy_headers)
    else:
        monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)

    from app import create_app
    from app.config import Config

    flask_app = create_app(Config)
    flask_app.config.update(
        TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False
    )
    flask_app.auth_ops.create_local_user("admin", "adminpass123", role="admin")
    _register_echo_route(flask_app)
    return flask_app


def _echo_forwarded(flask_app):
    client = flask_app.test_client()
    client.post("/login", data={"username": "admin", "password": "adminpass123"})
    response = client.get(
        "/__test/echo-oidc-redirect-uri",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "public.example.com",
        },
    )
    return response.data.decode()


def test_trust_proxy_headers_enabled_by_default_honors_forwarded_headers(
    tmp_path, monkeypatch
):
    # TRUST_PROXY_HEADERS now defaults to "1" since this app always runs
    # behind a reverse proxy in its supported deployments.
    flask_app = _make_app(tmp_path, monkeypatch)

    assert (
        _echo_forwarded(flask_app) == "https://public.example.com/login/oidc/callback"
    )


def test_trust_proxy_headers_explicitly_disabled_ignores_forwarded_headers(
    tmp_path, monkeypatch
):
    flask_app = _make_app(tmp_path, monkeypatch, trust_proxy_headers="0")

    assert _echo_forwarded(flask_app).startswith("http://localhost/")
