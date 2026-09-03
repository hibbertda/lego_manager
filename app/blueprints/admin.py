from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.auth_ops import VALID_ROLES
from app.decorators import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@admin_required
def index():
    return redirect(url_for("admin.users"))


@admin_bp.route("/config")
@login_required
@admin_required
def config():
    # Legacy URL from before the admin area was split into separate pages.
    return redirect(url_for("admin.users"))


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    all_users = current_app.auth_ops.list_users()
    return render_template("admin_users.html", users=all_users, roles=VALID_ROLES)


@admin_bp.route("/sso")
@login_required
@admin_required
def sso():
    provider = current_app.auth_ops.get_oidc_provider()
    return render_template("admin_sso.html", provider=provider, roles=VALID_ROLES)


@admin_bp.route("/brickset")
@login_required
@admin_required
def brickset():
    settings = current_app.db_ops.get_brickset_settings()
    return render_template(
        "admin_brickset.html",
        settings=settings,
        env_api_key_set=bool(current_app.config.get("BRICKSET_API_KEY")),
    )


@admin_bp.route("/brickset", methods=["POST"])
@login_required
@admin_required
def update_brickset():
    api_key = request.form.get("api_key", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    existing = current_app.db_ops.get_brickset_settings()
    if not api_key and existing:
        api_key = existing["api_key"]  # keep existing key if left blank
    if not password and existing:
        password = existing["password"]  # keep existing password if left blank

    if not api_key:
        flash("An API key is required.", "error")
        return redirect(url_for("admin.brickset"))

    current_app.db_ops.save_brickset_settings(
        api_key=api_key, username=username, password=password
    )
    current_app.brickset_api.configure(api_key)
    flash("Brickset API settings saved.", "success")
    return redirect(url_for("admin.brickset"))


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def update_user_role(user_id):
    role = request.form.get("role")
    if role not in VALID_ROLES:
        flash("Invalid role.", "error")
        return redirect(url_for("admin.users"))

    if user_id == current_user.id and role != "admin":
        # Prevent an admin from locking themselves out if they are the last admin.
        if current_app.auth_ops.count_active_admins() <= 1:
            flash("Cannot remove the last remaining admin.", "error")
            return redirect(url_for("admin.users"))

    current_app.auth_ops.update_user_role(user_id, role)
    flash("Role updated.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/active", methods=["POST"])
@login_required
@admin_required
def toggle_user_active(user_id):
    is_active = request.form.get("is_active") == "1"

    if user_id == current_user.id and not is_active:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin.users"))

    target = current_app.auth_ops.get_user_by_id(user_id)
    if (
        target
        and target["role"] == "admin"
        and not is_active
        and current_app.auth_ops.count_active_admins() <= 1
    ):
        flash("Cannot deactivate the last remaining admin.", "error")
        return redirect(url_for("admin.users"))

    current_app.auth_ops.set_user_active(user_id, is_active)
    flash("Account updated.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.users"))

    target = current_app.auth_ops.get_user_by_id(user_id)
    if (
        target
        and target["role"] == "admin"
        and current_app.auth_ops.count_active_admins() <= 1
    ):
        flash("Cannot delete the last remaining admin.", "error")
        return redirect(url_for("admin.users"))

    current_app.auth_ops.delete_user(user_id)
    flash("Account deleted.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/create", methods=["POST"])
@login_required
@admin_required
def create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "user")

    if role not in VALID_ROLES:
        role = "user"

    if not username or not password:
        flash("Username and password are required.", "error")
    elif len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
    elif current_app.auth_ops.get_user_by_username(username):
        flash("That username is already taken.", "error")
    else:
        current_app.auth_ops.create_local_user(username, password, role=role)
        flash("User created.", "success")

    return redirect(url_for("admin.users"))


@admin_bp.route("/oidc", methods=["POST"])
@login_required
@admin_required
def update_oidc():
    name = request.form.get("name", "OIDC Provider").strip() or "OIDC Provider"
    issuer = request.form.get("issuer", "").strip()
    client_id = request.form.get("client_id", "").strip()
    client_secret = request.form.get("client_secret", "").strip()
    scopes = (
        request.form.get("scopes", "openid profile email").strip()
        or "openid profile email"
    )
    default_role = request.form.get("default_role", "user")
    enabled = request.form.get("enabled") == "1"
    disable_local_login = request.form.get("disable_local_login") == "1"

    if default_role not in VALID_ROLES:
        default_role = "user"

    existing = current_app.auth_ops.get_oidc_provider()
    if not client_secret and existing:
        client_secret = existing["client_secret"]  # keep existing secret if left blank

    if enabled and not (issuer and client_id and client_secret):
        flash(
            "Issuer, client ID, and client secret are required to enable SSO.", "error"
        )
        return redirect(url_for("admin.sso"))

    if disable_local_login and not enabled:
        flash("SSO must be enabled to disable local login.", "error")
        return redirect(url_for("admin.sso"))

    current_app.auth_ops.save_oidc_provider(
        name=name,
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        enabled=enabled,
        default_role=default_role,
        disable_local_login=disable_local_login,
    )
    current_app.oidc_oauth.reload()
    flash("SSO configuration saved.", "success")
    return redirect(url_for("admin.sso"))
