import logging

from authlib.integrations.base_client.errors import OAuthError
from flask import Blueprint, current_app, redirect, url_for
from flask_login import login_user

from app import limiter
from app.auth_ops import OidcUsernameConflictError, OidcUserNotProvisionedError
from app.user import User

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)

# NOTE: this blueprint used to also hold the Jinja-rendered /setup, /login,
# /login/local, and /logout views. Those have been fully replaced by the
# React SPA (see app/blueprints/spa.py) talking to the equivalent JSON
# endpoints in app/blueprints/api.py (/api/setup, /api/login,
# /api/login/local, /api/logout). Only the OIDC redirect dance remains here,
# since an OAuth2 authorization-code flow requires real server-rendered
# redirects and can't be done via a JS fetch() call.


def _login_redirect(error: str | None = None):
    """Send the browser back to React's /login route. There's no Jinja
    flash-message banner anymore, so errors are passed as a query string the
    LoginPage reads and renders itself."""
    if error:
        return redirect(url_for("spa.index", subpath="login", error=error))
    return redirect(url_for("spa.index", subpath="login"))


@auth_bp.route("/login/oidc")
def oidc_login():
    provider = current_app.auth_ops.get_oidc_provider()
    if not provider or not provider["enabled"]:
        return _login_redirect("Single sign-on is not enabled.")

    redirect_uri = url_for("auth.oidc_callback", _external=True)
    return current_app.oidc_oauth.oidc.authorize_redirect(redirect_uri)


@auth_bp.route("/login/oidc/callback")
@limiter.limit("20 per minute")
def oidc_callback():
    provider = current_app.auth_ops.get_oidc_provider()
    if not provider or not provider["enabled"]:
        return _login_redirect("Single sign-on is not enabled.")

    client = current_app.oidc_oauth.oidc
    try:
        token = client.authorize_access_token()
    except OAuthError:
        # Covers MismatchingStateError (the state Authlib stored in the
        # session during /login/oidc can't be found/verified on this
        # request — e.g. the session cookie expired, the login link was
        # reused/replayed, or the browser blocked the cookie) as well as
        # error responses the provider itself redirects back with (denied
        # consent, expired code, etc). Either way this is a normal,
        # user-recoverable failure, not a server bug — log server-side for
        # diagnosis but don't surface a raw 500 to the user.
        logger.warning(
            "OIDC callback failed to exchange the authorization code", exc_info=True
        )
        return _login_redirect(
            "Single sign-on failed or the login session expired. Please try signing in again."
        )

    userinfo = token.get("userinfo") or client.userinfo(token=token)

    subject = userinfo.get("sub")
    if not subject:
        return _login_redirect("OIDC provider did not return a subject claim.")

    username = userinfo.get("preferred_username") or userinfo.get("email") or subject
    email = userinfo.get("email")

    try:
        user_data = current_app.auth_ops.get_or_create_oidc_user(
            oidc_subject=subject,
            username=username,
            email=email,
            default_role=provider["default_role"],
            auto_create_users=provider.get("auto_create_users", True),
        )
    except OidcUsernameConflictError as exc:
        # The username derived from the IdP's claims collides with an
        # existing account (e.g. a local admin account created via /setup
        # sharing a name with this identity in Authentik). Deliberately not
        # auto-linked: doing so on an unauthenticated callback based on a
        # username match alone would let anyone who controls a matching IdP
        # username take over an existing local account.
        logger.warning("OIDC login blocked by a username conflict: %s", exc)
        return _login_redirect(str(exc))
    except OidcUserNotProvisionedError as exc:
        # Automatic account creation is disabled and no account (real or
        # pre-authorized pending invite) exists for this identity yet — a
        # normal, expected outcome for an access-controlled deployment, not
        # a server error.
        logger.info("OIDC login denied: no account provisioned for %s", username)
        return _login_redirect(str(exc))

    if not user_data.get("is_active", True):
        return _login_redirect("This account has been disabled.")

    login_user(User(user_data))
    return redirect(url_for("spa.index", subpath="sets"))
