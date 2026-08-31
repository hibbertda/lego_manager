def test_no_users_redirects_to_setup(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/setup" in response.headers["Location"]


def test_setup_creates_admin_and_logs_in(app, client):
    response = client.post(
        "/setup",
        data={
            "username": "firstadmin",
            "password": "supersecret1",
            "confirm_password": "supersecret1",
        },
    )
    assert response.status_code == 302

    user = app.auth_ops.get_user_by_username("firstadmin")
    assert user is not None
    assert user["role"] == "admin"

    # Should now be logged in and able to reach the home page.
    home = client.get("/", follow_redirects=True)
    assert home.status_code == 200


def test_setup_unreachable_once_a_user_exists(admin_user, client):
    response = client.get("/setup", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_with_bad_credentials_fails(admin_user, client):
    response = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data


def test_login_with_good_credentials_succeeds(admin_user, client):
    response = client.post(
        "/login", data={"username": "admin", "password": "adminpass123"}, follow_redirects=False
    )
    assert response.status_code == 302

    home = client.get("/", follow_redirects=True)
    assert home.status_code == 200


def test_anonymous_request_redirects_to_login_when_users_exist(admin_user, client):
    response = client.get("/setlist", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_regular_user_cannot_access_admin_config(user_client):
    response = user_client.get("/admin/users")
    assert response.status_code == 403


def test_regular_user_cannot_delete_sets(app, user_client):
    app.db_ops.insert_set_data({
        "setID": 700, "number": "700", "name": "Protected Set", "year": 2024,
        "theme": "Test", "pieces": 1, "local_images": [], "local_instructions": [],
    })
    response = user_client.post("/set/700/delete")
    assert response.status_code == 403
    assert app.db_ops.get_set_by_id(700) is not None


def test_regular_user_can_view_sets(user_client):
    response = user_client.get("/setlist")
    assert response.status_code == 200


def test_admin_can_access_admin_config(admin_client):
    response = admin_client.get("/admin/users")
    assert response.status_code == 200
    assert b"User Management" in response.data


def test_admin_config_redirects_to_users_page(admin_client):
    response = admin_client.get("/admin/config", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/users")


def test_admin_can_access_sso_page(admin_client):
    response = admin_client.get("/admin/sso")
    assert response.status_code == 200
    assert b"Single Sign-On" in response.data


def test_regular_user_cannot_access_sso_page(user_client):
    response = user_client.get("/admin/sso")
    assert response.status_code == 403


def test_admin_can_access_brickset_page(admin_client):
    response = admin_client.get("/admin/brickset")
    assert response.status_code == 200
    assert b"Brickset API" in response.data


def test_regular_user_cannot_access_brickset_page(user_client):
    response = user_client.get("/admin/brickset")
    assert response.status_code == 403


def test_admin_can_save_brickset_settings(app, admin_client):
    response = admin_client.post(
        "/admin/brickset",
        data={"csrf_token": "", "api_key": "test-key-123", "username": "bob", "password": "secret"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    saved = app.db_ops.get_brickset_settings()
    assert saved["api_key"] == "test-key-123"
    assert saved["username"] == "bob"
    assert app.brickset_api.api_key == "test-key-123"


def test_saving_brickset_settings_without_api_key_keeps_existing(app, admin_client):
    app.db_ops.save_brickset_settings(api_key="original-key", username="", password="")
    response = admin_client.post(
        "/admin/brickset",
        data={"csrf_token": "", "api_key": "", "username": "alice", "password": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    saved = app.db_ops.get_brickset_settings()
    assert saved["api_key"] == "original-key"
    assert saved["username"] == "alice"


def test_saving_brickset_settings_requires_api_key_when_none_exists(admin_client):
    response = admin_client.post(
        "/admin/brickset",
        data={"csrf_token": "", "api_key": "", "username": "", "password": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"An API key is required" in response.data


def test_admin_can_create_and_delete_local_user(app, admin_client):
    response = admin_client.post(
        "/admin/users/create",
        data={"username": "newbie", "password": "newbiepass1", "role": "user"},
    )
    assert response.status_code == 302
    created = app.auth_ops.get_user_by_username("newbie")
    assert created is not None

    response = admin_client.post(f"/admin/users/{created['id']}/delete")
    assert response.status_code == 302
    assert app.auth_ops.get_user_by_id(created["id"]) is None


def test_admin_cannot_delete_last_remaining_admin(app, admin_client, admin_user):
    admin = app.auth_ops.get_user_by_username("admin")
    response = admin_client.post(f"/admin/users/{admin['id']}/delete")
    assert response.status_code == 302
    assert app.auth_ops.get_user_by_id(admin["id"]) is not None


def test_logout_requires_login_afterward(admin_client):
    response = admin_client.post("/logout", follow_redirects=False)
    assert response.status_code == 302

    response = admin_client.get("/setlist", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_page_hides_local_form_when_disabled(app, admin_user, client):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=True,
    )
    response = client.get("/login")
    assert response.status_code == 200
    assert b'name="username"' not in response.data
    assert b"Sign in with Authentik" in response.data
    assert b"/login/local" in response.data


def test_login_page_shows_local_form_when_sso_disabled(app, admin_user, client):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=False,
        disable_local_login=False,
    )
    response = client.get("/login")
    assert response.status_code == 200
    assert b'name="username"' in response.data


def test_local_login_post_rejected_on_main_login_when_disabled(app, admin_user, client):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=True,
    )
    response = client.post(
        "/login", data={"username": "admin", "password": "adminpass123"}, follow_redirects=False
    )
    assert response.status_code == 302
    # Should not be logged in.
    home = client.get("/", follow_redirects=False)
    assert home.status_code == 302
    assert "/login" in home.headers["Location"]


def test_fallback_local_login_still_works_when_main_form_disabled(app, admin_user, client):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=True,
    )
    response = client.get("/login/local")
    assert response.status_code == 200
    assert b'name="username"' in response.data

    response = client.post(
        "/login/local", data={"username": "admin", "password": "adminpass123"}, follow_redirects=False
    )
    assert response.status_code == 302

    home = client.get("/", follow_redirects=True)
    assert home.status_code == 200


def test_cannot_disable_local_login_without_enabling_sso(admin_client):
    response = admin_client.post(
        "/admin/oidc",
        data={
            "name": "Authentik",
            "issuer": "https://auth.example.com/o/lego/",
            "client_id": "cid",
            "client_secret": "csecret",
            "scopes": "openid profile email",
            "default_role": "user",
            "disable_local_login": "1",
            # "enabled" omitted -> not enabled
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"SSO must be enabled to disable local login" in response.data
