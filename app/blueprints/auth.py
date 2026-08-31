from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app import limiter
from app.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run bootstrap: create the initial admin account.

    Only reachable while no users exist yet; once an account is created this
    route redirects to /login for all future requests.
    """
    if current_app.auth_ops.has_any_users():
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            user_id = current_app.auth_ops.create_local_user(username, password, role="admin")
            login_user(User(current_app.auth_ops.get_user_by_id(user_id)))
            flash("Admin account created. Welcome!", "success")
            return redirect(url_for("main.index"))

    return render_template("setup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_app.auth_ops.has_any_users() is False:
        return redirect(url_for("auth.setup"))

    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    oidc_provider = current_app.auth_ops.get_oidc_provider()
    oidc_enabled = bool(oidc_provider and oidc_provider["enabled"])
    local_disabled = oidc_enabled and bool(oidc_provider.get("disable_local_login"))

    if request.method == "POST":
        if local_disabled:
            # Local login page is disabled while SSO is active; the fallback
            # route at /login/local remains available for break-glass access.
            flash("Local login is disabled. Use single sign-on, or the fallback login if needed.", "error")
            return redirect(url_for("auth.login"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user_data = current_app.auth_ops.verify_local_login(username, password)
        if user_data:
            login_user(User(user_data))
            next_url = request.args.get("next") or url_for("main.index")
            return redirect(next_url)
        flash("Invalid username or password.", "error")

    return render_template(
        "login.html",
        oidc_enabled=oidc_enabled,
        oidc_name=oidc_provider["name"] if oidc_provider else None,
        local_disabled=local_disabled,
        fallback_url=url_for("auth.local_login") if local_disabled else None,
    )


@auth_bp.route("/login/local", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def local_login():
    """Fallback local-login form, always reachable even when the main /login
    page hides the local form (disable_local_login). Use this if the external
    OIDC provider is unavailable."""
    if current_app.auth_ops.has_any_users() is False:
        return redirect(url_for("auth.setup"))

    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user_data = current_app.auth_ops.verify_local_login(username, password)
        if user_data:
            login_user(User(user_data))
            next_url = request.args.get("next") or url_for("main.index")
            return redirect(next_url)
        flash("Invalid username or password.", "error")

    return render_template(
        "login.html",
        oidc_enabled=False,
        oidc_name=None,
        local_disabled=False,
        fallback_url=None,
        is_fallback=True,
    )


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@auth_bp.route("/login/oidc")
def oidc_login():
    provider = current_app.auth_ops.get_oidc_provider()
    if not provider or not provider["enabled"]:
        flash("Single sign-on is not enabled.", "error")
        return redirect(url_for("auth.login"))

    redirect_uri = url_for("auth.oidc_callback", _external=True)
    return current_app.oidc_oauth.oidc.authorize_redirect(redirect_uri)


@auth_bp.route("/login/oidc/callback")
@limiter.limit("20 per minute")
def oidc_callback():
    provider = current_app.auth_ops.get_oidc_provider()
    if not provider or not provider["enabled"]:
        flash("Single sign-on is not enabled.", "error")
        return redirect(url_for("auth.login"))

    client = current_app.oidc_oauth.oidc
    token = client.authorize_access_token()
    userinfo = token.get("userinfo") or client.userinfo(token=token)

    subject = userinfo.get("sub")
    if not subject:
        flash("OIDC provider did not return a subject claim.", "error")
        return redirect(url_for("auth.login"))

    username = userinfo.get("preferred_username") or userinfo.get("email") or subject
    email = userinfo.get("email")

    user_data = current_app.auth_ops.get_or_create_oidc_user(
        oidc_subject=subject,
        username=username,
        email=email,
        default_role=provider["default_role"],
    )
    if not user_data.get("is_active", True):
        flash("This account has been disabled.", "error")
        return redirect(url_for("auth.login"))

    login_user(User(user_data))
    return redirect(url_for("main.index"))
