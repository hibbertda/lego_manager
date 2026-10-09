def test_no_users_needs_setup(client):
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.get_json()["needs_setup"] is True


def test_setup_creates_admin_and_logs_in(app, client):
    response = client.post(
        "/api/setup",
        json={
            "username": "firstadmin",
            "password": "supersecret1",
            "confirm_password": "supersecret1",
        },
    )
    assert response.status_code == 201

    user = app.auth_ops.get_user_by_username("firstadmin")
    assert user is not None
    assert user["role"] == "admin"
    assert response.get_json()["authenticated"] is True


def test_setup_unreachable_once_a_user_exists(admin_user, client):
    response = client.post(
        "/api/setup",
        json={
            "username": "second",
            "password": "supersecret1",
            "confirm_password": "supersecret1",
        },
    )
    assert response.status_code == 409


def test_login_with_bad_credentials_fails(admin_user, client):
    response = client.post(
        "/api/login", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401
    assert b"Invalid username or password" in response.data


def test_login_with_good_credentials_succeeds(admin_user, client):
    response = client.post(
        "/api/login", json={"username": "admin", "password": "adminpass123"}
    )
    assert response.status_code == 200
    assert response.get_json()["authenticated"] is True


def test_anonymous_request_to_api_requires_login_when_users_exist(admin_user, client):
    response = client.get("/api/sets")
    assert response.status_code == 401


def test_regular_user_cannot_access_admin_config(user_client):
    response = user_client.get("/api/admin/users")
    assert response.status_code == 403


def test_regular_user_cannot_delete_sets(app, user_client):
    app.db_ops.insert_set_data(
        {
            "setID": 700,
            "number": "700",
            "name": "Protected Set",
            "year": 2024,
            "theme": "Test",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    response = user_client.delete("/api/sets/700")
    assert response.status_code == 403
    assert app.db_ops.get_set_by_id(700) is not None


def test_regular_user_can_view_sets(user_client):
    response = user_client.get("/api/sets")
    assert response.status_code == 200


def test_admin_can_access_admin_config(admin_client):
    response = admin_client.get("/api/admin/users")
    assert response.status_code == 200
    assert response.get_json()["users"]


def test_admin_can_access_sso_page(admin_client):
    response = admin_client.get("/api/admin/sso")
    assert response.status_code == 200


def test_regular_user_cannot_access_sso_page(user_client):
    response = user_client.get("/api/admin/sso")
    assert response.status_code == 403


def test_admin_can_access_brickset_page(admin_client):
    response = admin_client.get("/api/admin/brickset")
    assert response.status_code == 200


def test_regular_user_cannot_access_brickset_page(user_client):
    response = user_client.get("/api/admin/brickset")
    assert response.status_code == 403


def test_admin_can_save_brickset_settings(app, admin_client):
    response = admin_client.post(
        "/api/admin/brickset",
        json={"api_key": "test-key-123", "username": "bob", "password": "secret"},
    )
    assert response.status_code == 200
    saved = app.db_ops.get_brickset_settings()
    assert saved["api_key"] == "test-key-123"
    assert saved["username"] == "bob"
    assert app.brickset_api.api_key == "test-key-123"


def test_saving_brickset_settings_without_api_key_keeps_existing(app, admin_client):
    app.db_ops.save_brickset_settings(api_key="original-key", username="", password="")
    response = admin_client.post(
        "/api/admin/brickset",
        json={"api_key": "", "username": "alice", "password": ""},
    )
    assert response.status_code == 200
    saved = app.db_ops.get_brickset_settings()
    assert saved["api_key"] == "original-key"
    assert saved["username"] == "alice"


def test_saving_brickset_settings_requires_api_key_when_none_exists(admin_client):
    response = admin_client.post(
        "/api/admin/brickset",
        json={"api_key": "", "username": "", "password": ""},
    )
    assert response.status_code == 400
    assert b"An API key is required" in response.data


def test_admin_can_create_and_delete_local_user(app, admin_client):
    response = admin_client.post(
        "/api/admin/users",
        json={"username": "newbie", "password": "newbiepass1", "role": "user"},
    )
    assert response.status_code == 201
    created = app.auth_ops.get_user_by_username("newbie")
    assert created is not None

    response = admin_client.delete(f"/api/admin/users/{created['id']}")
    assert response.status_code == 200
    assert app.auth_ops.get_user_by_id(created["id"]) is None


def test_admin_cannot_delete_last_remaining_admin(app, admin_client, admin_user):
    admin = app.auth_ops.get_user_by_username("admin")
    response = admin_client.delete(f"/api/admin/users/{admin['id']}")
    assert response.status_code == 400
    assert app.auth_ops.get_user_by_id(admin["id"]) is not None


def test_logout_requires_login_afterward(admin_client):
    response = admin_client.post("/api/logout")
    assert response.status_code == 204

    response = admin_client.get("/api/sets")
    assert response.status_code == 401


def test_session_reports_local_disabled_when_sso_enforced(app, admin_user, client):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=True,
    )
    response = client.get("/api/session")
    assert response.status_code == 200
    body = response.get_json()
    assert body["oidc_enabled"] is True
    assert body["local_disabled"] is True


def test_session_reports_local_enabled_when_sso_disabled(app, admin_user, client):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=False,
        disable_local_login=False,
    )
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.get_json()["local_disabled"] is False


def test_login_rejected_when_disabled(app, admin_user, client):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=True,
    )
    response = client.post(
        "/api/login", json={"username": "admin", "password": "adminpass123"}
    )
    assert response.status_code == 403

    # Should not be logged in.
    session = client.get("/api/session").get_json()
    assert session["authenticated"] is False


def test_fallback_local_login_still_works_when_main_form_disabled(
    app, admin_user, client
):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=True,
    )
    response = client.post(
        "/api/login/local", json={"username": "admin", "password": "adminpass123"}
    )
    assert response.status_code == 200
    assert response.get_json()["authenticated"] is True


def test_cannot_disable_local_login_without_enabling_sso(admin_client):
    response = admin_client.post(
        "/api/admin/sso",
        json={
            "name": "Authentik",
            "issuer": "https://auth.example.com/o/lego/",
            "client_id": "cid",
            "client_secret": "csecret",
            "scopes": "openid profile email",
            "default_role": "user",
            "disable_local_login": True,
            "enabled": False,
        },
    )
    assert response.status_code == 400
    assert b"SSO must be enabled to disable local login" in response.data


def test_oidc_callback_mismatching_state_redirects_to_login_with_error(app, client):
    from authlib.integrations.base_client.errors import MismatchingStateError

    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=False,
    )
    app.oidc_oauth.reload()

    def _raise_mismatch(*args, **kwargs):
        raise MismatchingStateError()

    app.oidc_oauth.oidc.authorize_access_token = _raise_mismatch

    response = client.get(
        "/login/oidc/callback?state=bad&code=irrelevant", follow_redirects=False
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert "error=" in response.headers["Location"]


def test_oidc_callback_username_conflict_redirects_with_error(app, client):
    app.auth_ops.create_local_user(
        username="daniel", password="danielpass1", role="admin"
    )
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=False,
    )
    app.oidc_oauth.reload()

    fake_userinfo = {"sub": "authentik-subject-123", "preferred_username": "daniel"}
    app.oidc_oauth.oidc.authorize_access_token = lambda *a, **k: {
        "userinfo": fake_userinfo
    }

    response = client.get(
        "/login/oidc/callback?state=irrelevant&code=irrelevant",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    # No account should have been left half-created for the OIDC subject.
    assert app.auth_ops.get_user_by_username("daniel")["auth_provider"] == "local"


def test_oidc_callback_denied_when_auto_create_disabled_and_no_account(app, client):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=False,
        auto_create_users=False,
    )
    app.oidc_oauth.reload()

    fake_userinfo = {"sub": "authentik-subject-999", "preferred_username": "newperson"}
    app.oidc_oauth.oidc.authorize_access_token = lambda *a, **k: {
        "userinfo": fake_userinfo
    }

    response = client.get(
        "/login/oidc/callback?state=irrelevant&code=irrelevant",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert app.auth_ops.get_user_by_username("newperson") is None


def test_oidc_callback_links_pending_invite_when_auto_create_disabled(app, client):
    app.auth_ops.create_pending_oidc_user("preauthorized", role="user")
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=False,
        auto_create_users=False,
    )
    app.oidc_oauth.reload()

    fake_userinfo = {
        "sub": "authentik-subject-111",
        "preferred_username": "preauthorized",
        "email": "person@example.com",
    }
    app.oidc_oauth.oidc.authorize_access_token = lambda *a, **k: {
        "userinfo": fake_userinfo
    }

    response = client.get(
        "/login/oidc/callback?state=irrelevant&code=irrelevant",
        follow_redirects=False,
    )

    assert response.status_code == 302
    linked = app.auth_ops.get_user_by_username("preauthorized")
    assert linked["auth_provider"] == "oidc"
    assert linked["oidc_subject"] == "authentik-subject-111"
    assert linked["email"] == "person@example.com"

    # A second login from the same subject should reuse the now-linked
    # account rather than erroring or re-linking.
    client.post("/api/logout")
    response2 = client.get(
        "/login/oidc/callback?state=irrelevant&code=irrelevant",
        follow_redirects=False,
    )
    assert response2.status_code == 302


def test_oidc_callback_auto_creates_when_enabled_default(app, client):
    app.auth_ops.save_oidc_provider(
        name="Authentik",
        issuer="https://auth.example.com/application/o/lego/",
        client_id="cid",
        client_secret="csecret",
        enabled=True,
        disable_local_login=False,
        auto_create_users=True,
    )
    app.oidc_oauth.reload()

    fake_userinfo = {"sub": "authentik-subject-222", "preferred_username": "brandnew"}
    app.oidc_oauth.oidc.authorize_access_token = lambda *a, **k: {
        "userinfo": fake_userinfo
    }

    response = client.get(
        "/login/oidc/callback?state=irrelevant&code=irrelevant",
        follow_redirects=False,
    )

    assert response.status_code == 302
    created = app.auth_ops.get_user_by_username("brandnew")
    assert created is not None
    assert created["auth_provider"] == "oidc"
    assert created["oidc_subject"] == "authentik-subject-222"


def test_admin_can_pre_authorize_sso_user(app, admin_client):
    response = admin_client.post(
        "/api/admin/users/pending-sso",
        json={"username": "futureuser", "role": "user"},
    )
    assert response.status_code == 201
    assert b"pre-authorized" in response.data.lower()

    pending = app.auth_ops.get_user_by_username("futureuser")
    assert pending is not None
    assert pending["auth_provider"] == "oidc"
    assert pending["oidc_subject"] is None


def test_admin_cannot_pre_authorize_duplicate_sso_username(
    app, admin_client, admin_user
):
    response = admin_client.post(
        "/api/admin/users/pending-sso",
        json={"username": "admin", "role": "user"},
    )
    assert response.status_code == 400
    assert b"already taken" in response.data
