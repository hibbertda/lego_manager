import pytest


@pytest.fixture()
def db_ops(tmp_path):
    from sql_ops import DatabaseOps

    db_path = tmp_path / "test_lego.db"
    return DatabaseOps(str(db_path))


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test_lego.db"))
    monkeypatch.setenv("SETS_DIR", str(tmp_path / "sets"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("BRICKSET_API_KEY", "test-key")
    monkeypatch.setenv("BRICKSET_USERNAME", "test-user")
    monkeypatch.setenv("BRICKSET_PASSWORD", "test-pass")

    from app import create_app
    from app.config import Config

    flask_app = create_app(Config)
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_user(app):
    app.auth_ops.create_local_user("admin", "adminpass123", role="admin")


@pytest.fixture()
def regular_user(app):
    app.auth_ops.create_local_user("bob", "bobpass123", role="user")


@pytest.fixture()
def admin_client(app, admin_user):
    """A test client already logged in as an admin user."""
    test_client = app.test_client()
    test_client.post("/login", data={"username": "admin", "password": "adminpass123"})
    return test_client


@pytest.fixture()
def user_client(app, admin_user, regular_user):
    """A test client already logged in as a non-admin user.

    Depends on admin_user existing too, since the app requires at least one
    account before /login is reachable at all (otherwise it redirects to /setup).
    """
    test_client = app.test_client()
    test_client.post("/login", data={"username": "bob", "password": "bobpass123"})
    return test_client
