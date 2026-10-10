import os
import shutil
from functools import wraps
from typing import Any

from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFError, generate_csrf
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app import label_ops, limiter
from app.auth_ops import VALID_ROLES
from app.decorators import admin_required
from app.sql_ops import (
    BUILD_STATUS_META,
    DEFAULT_SORT,
    OWNED_BUILD_STATUSES,
    SORT_LABELS,
    VALID_BUILD_STATUSES,
)
from app.user import User

api_bp = Blueprint("api", __name__, url_prefix="/api")

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ALLOWED_INSTRUCTION_EXTENSIONS = {".pdf"}
_PILLOW_FORMATS_BY_EXT = {
    ".png": {"PNG"},
    ".jpg": {"JPEG"},
    ".jpeg": {"JPEG"},
    ".gif": {"GIF"},
    ".webp": {"WEBP"},
}


def _json_error(message: str, status: int):
    return jsonify(error=message), status


@api_bp.record_once
def _install_api_auth_gate(setup_state):
    app = setup_state.app
    funcs = app.before_request_funcs.setdefault(None, [])
    for idx, func in enumerate(funcs):
        if getattr(func, "_api_wrapper_installed", False):
            return
        if getattr(func, "__name__", "") != "_require_login":
            continue

        @wraps(func)
        def _api_aware_require_login(*args, __func=func, __app=app, **kwargs):
            endpoint = request.endpoint or ""
            if endpoint.startswith("api."):
                if endpoint in {
                    "api.session",
                    "api.setup",
                    "api.login",
                    "api.login_local",
                }:
                    return None
                if not __app.auth_ops.has_any_users():
                    return _json_error("Initial setup is required.", 403)
                if not current_user.is_authenticated:
                    return _json_error("Authentication required.", 401)
                return None
            return __func(*args, **kwargs)

        _api_aware_require_login._api_wrapper_installed = True
        funcs[idx] = _api_aware_require_login
        return


# Mirrors app/blueprints/sets.py's helpers of the same name; keep in sync manually.
def _has_allowed_extension(filename: str, allowed: set) -> bool:
    return os.path.splitext(filename)[1].lower() in allowed


# Mirrors app/blueprints/sets.py's helpers of the same name; keep in sync manually.
def _is_valid_image(file_storage, ext: str) -> bool:
    """Verify the uploaded file's actual bytes decode as an image matching its
    extension, not just that the filename looks right."""
    try:
        file_storage.stream.seek(0)
        with Image.open(file_storage.stream) as img:
            img.verify()
        file_storage.stream.seek(0)
        with Image.open(file_storage.stream) as img:
            fmt = img.format
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    finally:
        file_storage.stream.seek(0)
    return fmt in _PILLOW_FORMATS_BY_EXT.get(ext, set())


# Mirrors app/blueprints/sets.py's helpers of the same name; keep in sync manually.
def _is_valid_pdf(file_storage) -> bool:
    """Cheap magic-byte check: real PDFs start with the '%PDF-' header."""
    try:
        file_storage.stream.seek(0)
        header = file_storage.stream.read(5)
    finally:
        file_storage.stream.seek(0)
    return header == b"%PDF-"


# Mirrors app/blueprints/sets.py's helpers of the same name; keep in sync manually.
def _regenerate_label(set_id: int) -> None:
    """(Re)generate a set's storage-box label from its current DB data."""
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return
    try:
        label_ops.generate_label(
            set_data,
            current_app.config["SETS_DIR"],
            current_app.config["APP_BASE_URL"],
        )
    except Exception:
        current_app.logger.exception("Failed to generate label for set %s", set_id)


@api_bp.errorhandler(401)
def _handle_401(_error):
    return _json_error("Authentication required.", 401)


@api_bp.errorhandler(403)
def _handle_403(_error):
    return _json_error("Forbidden.", 403)


@api_bp.errorhandler(404)
def _handle_404(_error):
    return _json_error("Not found", 404)


@api_bp.errorhandler(CSRFError)
def _handle_csrf(error):
    return _json_error(error.description, 400)


def _request_payload() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _payload_value(payload: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in payload:
        return payload.get(key)
    return request.form.get(key, default)


def _string_value(payload: dict[str, Any], key: str, default: str = "") -> str:
    value = _payload_value(payload, key, default)
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _bool_value(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    value = _payload_value(payload, key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(default)


def _coerce_nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _page_arg() -> int:
    return max(1, request.args.get("page", 1, type=int) or 1)


def _serialize_user(user_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not user_data:
        return None
    return {
        "id": user_data["id"],
        "username": user_data["username"],
        "email": user_data.get("email"),
        "role": user_data["role"],
        "is_admin": user_data["role"] == "admin",
        "auth_provider": user_data["auth_provider"],
    }


def _session_payload() -> dict[str, Any]:
    provider = current_app.auth_ops.get_oidc_provider()
    needs_setup = current_app.auth_ops.has_any_users() is False
    payload = {
        "authenticated": current_user.is_authenticated,
        "needs_setup": needs_setup,
        "user": (
            _serialize_user(current_app.auth_ops.get_user_by_id(current_user.id))
            if current_user.is_authenticated
            else None
        ),
        "csrf_token": generate_csrf(),
        "brickset_configured": bool(current_app.brickset_api.api_key),
        "oidc_enabled": bool(provider and provider["enabled"]),
        "oidc_name": provider["name"] if provider else None,
        "local_disabled": bool(
            provider and provider["enabled"] and provider.get("disable_local_login")
        ),
    }
    if current_user.is_authenticated:
        payload["owned_set_count"] = current_app.db_ops.count_owned_sets()
    return payload


def _set_image_url(set_data: dict[str, Any]) -> str | None:
    if set_data.get("local_images"):
        return url_for("sets.custom_static", filename=set_data["local_images"][0])
    return None


def _set_label_image_url(
    set_data: dict[str, Any], has_label: bool | None = None
) -> str | None:
    if has_label is None:
        has_label = label_ops.label_exists(set_data, current_app.config["SETS_DIR"])
    if not has_label:
        return None
    return url_for("sets.set_label_image", set_id=set_data["setID"])


def _serialize_set(set_data: dict[str, Any], detailed: bool = False) -> dict[str, Any]:
    build_status = set_data.get("build_status") or "not_started"
    status_meta = BUILD_STATUS_META[build_status]
    has_label = label_ops.label_exists(set_data, current_app.config["SETS_DIR"])
    serialized = {
        "setID": set_data["setID"],
        "setNumber": set_data.get("setNumber") or set_data.get("number"),
        "number": set_data.get("setNumber") or set_data.get("number"),
        "name": set_data.get("name"),
        "year": set_data.get("year"),
        "theme": set_data.get("theme"),
        "pieces": set_data.get("pieces"),
        "build_status": build_status,
        "build_page": set_data.get("build_page") or 0,
        "favorite": bool(set_data.get("favorite")),
        "location": set_data.get("location") or "",
        "image": _set_image_url(set_data),
        "status_label": status_meta["label"],
        "status_icon": status_meta["icon"],
        "status_badge_class": status_meta["badge_class"],
        "detail_url": f"/sets/{set_data['setID']}",
        "label_image_url": _set_label_image_url(set_data, has_label=has_label),
    }
    if detailed:
        serialized.update(
            {
                "launchDate": set_data.get("launchDate"),
                "instructions": set_data.get("instructions") or [],
                "local_images": set_data.get("local_images") or [],
                "local_image_urls": [
                    url_for("sets.custom_static", filename=img)
                    for img in (set_data.get("local_images") or [])
                ],
                "local_instructions": set_data.get("local_instructions") or [],
                "local_instruction_urls": [
                    url_for("sets.custom_static", filename=pdf)
                    for pdf in (set_data.get("local_instructions") or [])
                ],
                "build_photos": set_data.get("build_photos") or [],
                "build_photo_urls": [
                    url_for("sets.custom_static", filename=photo)
                    for photo in (set_data.get("build_photos") or [])
                ],
                "has_label": has_label,
                "label_url": (
                    url_for("sets.set_label", set_id=set_data["setID"])
                    if has_label
                    else None
                ),
            }
        )
    return serialized


def _parse_common_filters() -> dict[str, Any]:
    view = request.args.get("view", "grid")
    if view not in ("list", "grid"):
        view = "grid"
    theme = request.args.get("theme") or None
    favorite_only = request.args.get("favorite") == "1"
    sort = request.args.get("sort") or DEFAULT_SORT
    if sort not in SORT_LABELS:
        sort = DEFAULT_SORT
    return {
        "view": view,
        "theme": theme,
        "favorite_only": favorite_only,
        "sort": sort,
    }


def _parse_list_sets_filters() -> dict[str, Any]:
    filters = _parse_common_filters()
    build_status = request.args.get("status") or None
    if build_status not in OWNED_BUILD_STATUSES:
        build_status = None
    location = request.args.get("location") or None
    filters["build_status"] = build_status
    filters["location"] = location
    return filters


@api_bp.route("/session")
def session():
    return jsonify(_session_payload())


@api_bp.route("/setup", methods=["POST"])
def setup():
    if current_app.auth_ops.has_any_users():
        return _json_error("Initial setup has already been completed.", 409)

    payload = _request_payload()
    username = _string_value(payload, "username").strip()
    password = _string_value(payload, "password")
    confirm = _string_value(payload, "confirm_password")

    if not username or not password:
        return _json_error("Username and password are required.", 400)
    if password != confirm:
        return _json_error("Passwords do not match.", 400)
    if len(password) < 8:
        return _json_error("Password must be at least 8 characters.", 400)

    user_id = current_app.auth_ops.create_local_user(username, password, role="admin")
    login_user(User(current_app.auth_ops.get_user_by_id(user_id)))
    return jsonify(_session_payload()), 201


@api_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_app.auth_ops.has_any_users() is False:
        return _json_error("Initial setup is required before logging in.", 403)
    if current_user.is_authenticated:
        return jsonify(_session_payload())

    oidc_provider = current_app.auth_ops.get_oidc_provider()
    oidc_enabled = bool(oidc_provider and oidc_provider["enabled"])
    local_disabled = oidc_enabled and bool(oidc_provider.get("disable_local_login"))
    if local_disabled:
        return _json_error(
            "Local login is disabled. Use single sign-on, or the fallback login if needed.",
            403,
        )

    payload = _request_payload()
    username = _string_value(payload, "username").strip()
    password = _string_value(payload, "password")
    user_data = current_app.auth_ops.verify_local_login(username, password)
    if not user_data:
        return _json_error("Invalid username or password.", 401)

    login_user(User(user_data))
    return jsonify(_session_payload())


@api_bp.route("/login/local", methods=["POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login_local():
    """Fallback local-login endpoint, always reachable even when SSO is
    configured with disable_local_login — use if the external OIDC provider
    is unavailable. Deliberately bypasses the local_disabled gate in /login."""
    if current_app.auth_ops.has_any_users() is False:
        return _json_error("Initial setup is required before logging in.", 403)
    if current_user.is_authenticated:
        return jsonify(_session_payload())

    payload = _request_payload()
    username = _string_value(payload, "username").strip()
    password = _string_value(payload, "password")
    user_data = current_app.auth_ops.verify_local_login(username, password)
    if not user_data:
        return _json_error("Invalid username or password.", 401)

    login_user(User(user_data))
    return jsonify(_session_payload())


@api_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return "", 204


@api_bp.route("/sets")
@login_required
def list_sets():
    page = _page_arg()
    filters = _parse_list_sets_filters()
    per_page = current_app.config["SETS_PER_PAGE"]
    sets_data, total = current_app.db_ops.list_sets(
        page=page,
        per_page=per_page,
        theme=filters["theme"],
        build_status=filters["build_status"],
        favorite_only=filters["favorite_only"],
        sort=filters["sort"],
        location=filters["location"],
    )
    total_pages = max(1, (total + per_page - 1) // per_page)
    return jsonify(
        {
            "sets": [_serialize_set(set_data) for set_data in sets_data],
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "themes": current_app.db_ops.get_distinct_themes(),
            "locations": current_app.db_ops.get_distinct_locations(),
            "sort_labels": SORT_LABELS,
            "build_statuses": OWNED_BUILD_STATUSES,
        }
    )


@api_bp.route("/wishlist")
@login_required
def wishlist():
    page = _page_arg()
    filters = _parse_common_filters()
    per_page = current_app.config["SETS_PER_PAGE"]
    sets_data, total = current_app.db_ops.list_sets(
        page=page,
        per_page=per_page,
        theme=filters["theme"],
        build_status="wishlist",
        favorite_only=filters["favorite_only"],
        sort=filters["sort"],
    )
    total_pages = max(1, (total + per_page - 1) // per_page)
    return jsonify(
        {
            "sets": [_serialize_set(set_data) for set_data in sets_data],
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "themes": current_app.db_ops.get_distinct_themes(),
            "locations": [],
            "sort_labels": SORT_LABELS,
            "build_statuses": ["wishlist"],
        }
    )


@api_bp.route("/sets/<int(signed=True):set_id>")
@login_required
def set_detail(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)
    return jsonify(
        {
            "set": _serialize_set(set_data, detailed=True),
            "locations": current_app.db_ops.get_distinct_locations(),
        }
    )


@api_bp.route("/sets", methods=["POST"])
@login_required
def add_set():
    set_number = request.form.get("set_number", "").strip()
    if not set_number:
        return _json_error("Set number is required.", 400)

    initial_status = request.form.get("build_status") or "not_started"
    if initial_status not in VALID_BUILD_STATUSES:
        initial_status = "not_started"

    combined_data = current_app.brickset_api.get_combined_data(
        set_number,
        base_dir=current_app.config["SETS_DIR"],
        max_bytes=current_app.config["MAX_DOWNLOAD_BYTES"],
    )
    if not combined_data:
        return _json_error(
            "Failed to retrieve set data from Brickset. Check the set number, your Brickset API key, or add the set manually instead.",
            422,
        )

    new_set_ids = [
        set_row["setID"]
        for set_row in combined_data.get("sets", [])
        if set_row.get("setID") is not None
        and current_app.db_ops.get_set_by_id(set_row["setID"]) is None
    ]
    current_app.db_ops.insert_combined_data(combined_data)
    for added in combined_data.get("sets", []):
        if added.get("setID") is not None:
            _regenerate_label(added["setID"])
    if initial_status != "not_started":
        for new_set_id in new_set_ids:
            current_app.db_ops.update_build_status_only(new_set_id, initial_status)
    return jsonify(ok=True), 201


@api_bp.route("/sets/manual", methods=["POST"])
@login_required
def add_set_manual():
    set_number = request.form.get("set_number", "").strip()
    name = request.form.get("name", "").strip()
    year = request.form.get("year", type=int)
    theme = request.form.get("theme", "").strip() or None
    pieces = request.form.get("pieces", type=int)
    build_status = request.form.get("build_status") or "not_started"
    if build_status not in VALID_BUILD_STATUSES:
        build_status = "not_started"

    if not set_number or not name:
        return _json_error("Set number and name are required.", 400)

    safe_set_number = secure_filename(set_number)
    if not safe_set_number:
        return _json_error("Set number contains only invalid characters.", 400)

    sets_dir = current_app.config["SETS_DIR"]
    rel_images_dir = os.path.join(safe_set_number, "images")
    rel_instructions_dir = os.path.join(safe_set_number, "instructions")

    local_images = []
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        ext = os.path.splitext(image_file.filename)[1].lower()
        if not _has_allowed_extension(image_file.filename, ALLOWED_IMAGE_EXTENSIONS):
            return _json_error("Image must be a PNG, JPG, GIF, or WEBP file.", 400)
        if not _is_valid_image(image_file, ext):
            return _json_error("Image file is corrupt or is not a valid image.", 400)
        filename = secure_filename(image_file.filename)
        if not filename:
            return _json_error("Image filename is invalid.", 400)
        os.makedirs(os.path.join(sets_dir, rel_images_dir), exist_ok=True)
        rel_path = os.path.join(rel_images_dir, filename)
        image_file.save(os.path.join(sets_dir, rel_path))
        local_images.append(rel_path)

    local_instructions = []
    for pdf_file in request.files.getlist("instructions"):
        if pdf_file and pdf_file.filename:
            if not _has_allowed_extension(
                pdf_file.filename, ALLOWED_INSTRUCTION_EXTENSIONS
            ):
                return _json_error("Instructions must be PDF files.", 400)
            if not _is_valid_pdf(pdf_file):
                return _json_error("Instructions file is not a valid PDF.", 400)
            filename = secure_filename(pdf_file.filename)
            if not filename:
                return _json_error("Instructions filename is invalid.", 400)
            os.makedirs(os.path.join(sets_dir, rel_instructions_dir), exist_ok=True)
            rel_path = os.path.join(rel_instructions_dir, filename)
            pdf_file.save(os.path.join(sets_dir, rel_path))
            local_instructions.append(rel_path)

    set_id = current_app.db_ops.get_next_manual_set_id()
    set_data = {
        "setID": set_id,
        "number": safe_set_number,
        "numberVariant": 1,
        "name": name,
        "year": year,
        "theme": theme,
        "pieces": pieces,
        "launchDate": None,
        "instructions": [],
        "local_images": local_images,
        "local_instructions": local_instructions,
    }
    current_app.db_ops.insert_set_data(set_data)
    if build_status != "not_started":
        current_app.db_ops.update_build_status_only(set_id, build_status)
    _regenerate_label(set_id)
    return jsonify(ok=True, set_id=set_id), 201


@api_bp.route("/sets/<int(signed=True):set_id>/status", methods=["POST"])
@login_required
def update_status_only(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)

    payload = _request_payload()
    build_status = payload.get("build_status")
    if build_status not in VALID_BUILD_STATUSES:
        return _json_error("Invalid build status", 400)

    current_app.db_ops.update_build_status_only(set_id, build_status)
    return jsonify(ok=True, build_status=build_status)


@api_bp.route("/sets/<int(signed=True):set_id>/favorite", methods=["POST"])
@login_required
def toggle_favorite(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)

    favorite = current_app.db_ops.toggle_favorite(set_id)
    return jsonify(ok=True, favorite=favorite)


@api_bp.route("/sets/<int(signed=True):set_id>/location", methods=["POST"])
@login_required
def update_location(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)

    payload = _request_payload()
    location = _string_value(payload, "location").strip() or None
    current_app.db_ops.update_location(set_id, location)
    return jsonify(ok=True, location=location or "")


@api_bp.route("/sets/<int(signed=True):set_id>/progress", methods=["POST"])
@login_required
def update_progress(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)

    payload = _request_payload()
    build_status = payload.get("build_status", "not_started")
    if build_status not in VALID_BUILD_STATUSES:
        return _json_error("Invalid build status", 400)

    build_page = _coerce_nonnegative_int(payload.get("build_page", 0), default=0)
    current_app.db_ops.update_build_progress(set_id, build_page, build_status)
    return jsonify(ok=True)


@api_bp.route("/sets/<int(signed=True):set_id>/progress/page", methods=["POST"])
@login_required
def update_progress_page(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)

    payload = _request_payload()
    build_page = payload.get("build_page", 0)
    if not isinstance(build_page, int):
        return _json_error("build_page must be an integer", 400)

    current_app.db_ops.update_build_page(set_id, max(0, build_page))
    return jsonify(ok=True, build_page=max(0, build_page))


@api_bp.route("/sets/<int(signed=True):set_id>/photos", methods=["POST"])
@login_required
def upload_build_photos(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)

    photo_files = [f for f in request.files.getlist("photos") if f and f.filename]
    if not photo_files:
        return _json_error("At least one photo file is required.", 400)

    sets_dir = current_app.config["SETS_DIR"]
    safe_set_number = secure_filename(str(set_data["setNumber"]))
    rel_photos_dir = os.path.join(safe_set_number, "build_photos")

    new_photos = []
    for photo_file in photo_files:
        ext = os.path.splitext(photo_file.filename)[1].lower()
        if not _has_allowed_extension(photo_file.filename, ALLOWED_IMAGE_EXTENSIONS):
            return _json_error("Photos must be PNG, JPG, GIF, or WEBP files.", 400)
        if not _is_valid_image(photo_file, ext):
            return _json_error(
                "One of the uploaded photos is corrupt or is not a valid image.", 400
            )
        filename = secure_filename(photo_file.filename)
        if not filename:
            return _json_error("Photo filename is invalid.", 400)
        # Avoid clobbering an existing file with the same name (e.g. two
        # photos both named "IMG_0001.jpg" taken on different days).
        base, suffix = os.path.splitext(filename)
        candidate = filename
        counter = 1
        while os.path.exists(os.path.join(sets_dir, rel_photos_dir, candidate)):
            candidate = f"{base}_{counter}{suffix}"
            counter += 1
        os.makedirs(os.path.join(sets_dir, rel_photos_dir), exist_ok=True)
        rel_path = os.path.join(rel_photos_dir, candidate)
        photo_file.save(os.path.join(sets_dir, rel_path))
        new_photos.append(rel_path)

    current_app.db_ops.append_build_photos(set_id, new_photos)
    updated = current_app.db_ops.get_set_by_id(set_id)
    return (
        jsonify(
            ok=True,
            build_photos=updated["build_photos"],
            build_photo_urls=[
                url_for("sets.custom_static", filename=p)
                for p in updated["build_photos"]
            ],
        ),
        201,
    )


@api_bp.route("/sets/<int(signed=True):set_id>/photos", methods=["DELETE"])
@login_required
def delete_build_photo(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)

    payload = _request_payload()
    rel_path = _string_value(payload, "path")
    if not rel_path:
        return _json_error("A photo path is required.", 400)

    # remove_build_photo only succeeds for a path already present in this
    # set's stored build_photos list (itself always built server-side via
    # secure_filename), so there's no path-traversal risk here even though
    # rel_path comes straight from the request body.
    removed = current_app.db_ops.remove_build_photo(set_id, rel_path)
    if not removed:
        return _json_error("Photo not found.", 404)

    abs_path = os.path.join(current_app.config["SETS_DIR"], rel_path)
    if os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass

    return jsonify(ok=True)


@api_bp.route("/sets/<int(signed=True):set_id>/edit", methods=["POST"])
@login_required
@admin_required
def edit_set(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)

    name = request.form.get("name", "").strip()
    year = request.form.get("year", type=int)
    theme = request.form.get("theme", "").strip() or None
    pieces = request.form.get("pieces", type=int)

    if not name:
        return _json_error("Name is required.", 400)

    sets_dir = current_app.config["SETS_DIR"]
    safe_set_number = secure_filename(str(set_data["setNumber"]))
    rel_instructions_dir = os.path.join(safe_set_number, "instructions")

    new_instructions = []
    for pdf_file in request.files.getlist("instructions"):
        if pdf_file and pdf_file.filename:
            if not _has_allowed_extension(
                pdf_file.filename, ALLOWED_INSTRUCTION_EXTENSIONS
            ):
                return _json_error("Instructions must be PDF files.", 400)
            if not _is_valid_pdf(pdf_file):
                return _json_error("Instructions file is not a valid PDF.", 400)
            filename = secure_filename(pdf_file.filename)
            if not filename:
                return _json_error("Instructions filename is invalid.", 400)
            os.makedirs(os.path.join(sets_dir, rel_instructions_dir), exist_ok=True)
            rel_path = os.path.join(rel_instructions_dir, filename)
            pdf_file.save(os.path.join(sets_dir, rel_path))
            new_instructions.append(rel_path)

    current_app.db_ops.update_set_metadata(set_id, name, year, theme, pieces)
    if new_instructions:
        current_app.db_ops.append_local_instructions(set_id, new_instructions)
    _regenerate_label(set_id)
    return jsonify(ok=True)


@api_bp.route("/sets/<int(signed=True):set_id>/refresh", methods=["POST"])
@login_required
@admin_required
def refresh_set(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)
    if set_id < 0:
        return _json_error(
            "This set was added manually and isn't linked to Brickset.", 400
        )

    combined_data = current_app.brickset_api.get_combined_data(
        str(set_data["setNumber"]),
        base_dir=current_app.config["SETS_DIR"],
        max_bytes=current_app.config["MAX_DOWNLOAD_BYTES"],
    )
    if not combined_data:
        return _json_error(
            "Failed to refresh from Brickset. Check the Brickset API key and try again.",
            422,
        )

    current_app.db_ops.insert_combined_data(combined_data)
    _regenerate_label(set_id)
    return jsonify(ok=True)


def _serialize_parts(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "part_num": p["part_num"],
            "name": p["name"],
            "color_name": p["color_name"],
            "quantity": p["quantity"],
            "image_url": (
                url_for("sets.custom_static", filename=p["image_path"])
                if p.get("image_path")
                else None
            ),
        }
        for p in parts
    ]


def _serialize_minifigs(minifigs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "fig_num": m["fig_num"],
            "name": m["name"],
            "quantity": m["quantity"],
            "image_url": (
                url_for("sets.custom_static", filename=m["image_path"])
                if m.get("image_path")
                else None
            ),
        }
        for m in minifigs
    ]


@api_bp.route("/sets/<int(signed=True):set_id>/parts")
@login_required
def set_parts(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)
    parts = current_app.db_ops.get_set_parts(set_id)
    minifigs = current_app.db_ops.get_set_minifigs(set_id)
    return jsonify(
        parts=_serialize_parts(parts),
        minifigs=_serialize_minifigs(minifigs),
        synced=bool(set_data.get("parts_synced_at")),
        rebrickable_configured=bool(current_app.rebrickable_api.api_key),
    )


@api_bp.route("/sets/<int(signed=True):set_id>/parts/sync", methods=["POST"])
@login_required
@admin_required
def sync_set_parts(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)
    if not current_app.rebrickable_api.api_key:
        return _json_error(
            "Rebrickable isn't configured. Add an API key under Admin — Rebrickable API.",
            400,
        )

    set_number = str(set_data["setNumber"])
    sets_dir = current_app.config["SETS_DIR"]
    max_bytes = current_app.config["MAX_DOWNLOAD_BYTES"]

    parts = current_app.rebrickable_api.get_combined_set_parts(
        set_number, base_dir=sets_dir, max_bytes=max_bytes
    )
    if parts is None:
        return _json_error(
            "Failed to fetch parts from Rebrickable. Check the set number and API key and try again.",
            422,
        )
    # Minifigs are fetched best-effort: a failure here shouldn't discard an
    # otherwise-successful parts sync, since parts are the primary data and
    # some sets genuinely have zero minifigs rather than a fetch failure.
    minifigs = current_app.rebrickable_api.get_combined_set_minifigs(
        set_number, base_dir=sets_dir, max_bytes=max_bytes
    )

    current_app.db_ops.replace_set_parts(set_id, parts)
    current_app.db_ops.replace_set_minifigs(set_id, minifigs or [])
    current_app.db_ops.mark_parts_synced(set_id)
    return jsonify(
        parts=_serialize_parts(parts),
        minifigs=_serialize_minifigs(minifigs or []),
        synced=True,
    )


@api_bp.route("/sets/<int(signed=True):set_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_set(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        return _json_error("Not found", 404)

    deleted = current_app.db_ops.delete_set(set_id)
    if deleted:
        set_dir = os.path.join(
            current_app.config["SETS_DIR"], str(set_data["setNumber"])
        )
        if os.path.isdir(set_dir):
            shutil.rmtree(set_dir, ignore_errors=True)
    return jsonify(ok=True)


@api_bp.route("/search")
@login_required
def search():
    query = request.args.get("query", "")
    page = _page_arg()
    per_page = current_app.config["SETS_PER_PAGE"]
    sets_data, total = current_app.db_ops.search_sets(
        query, page=page, per_page=per_page
    )
    total_pages = max(1, (total + per_page - 1) // per_page)
    return jsonify(
        {
            "sets": [_serialize_set(set_data) for set_data in sets_data],
            "query": query,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        }
    )


@api_bp.route("/search/suggest")
@login_required
def search_suggest():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify(results=[], total=0)

    sets_data, total = current_app.db_ops.search_sets(query, page=1, per_page=8)
    results = [
        {
            "id": set_data["setID"],
            "name": set_data["name"],
            "setNumber": set_data["setNumber"],
            "year": set_data["year"],
            "theme": set_data["theme"],
            "image": _set_image_url(set_data),
            "url": f"/sets/{set_data['setID']}",
        }
        for set_data in sets_data
    ]
    return jsonify(results=results, total=total)


@api_bp.route("/admin/users")
@login_required
@admin_required
def users():
    return jsonify(users=current_app.auth_ops.list_users(), roles=VALID_ROLES)


@api_bp.route("/admin/users", methods=["POST"])
@login_required
@admin_required
def create_user():
    payload = _request_payload()
    username = _string_value(payload, "username").strip()
    password = _string_value(payload, "password")
    role = _string_value(payload, "role", "user")

    if role not in VALID_ROLES:
        role = "user"
    if not username or not password:
        return _json_error("Username and password are required.", 400)
    if len(password) < 8:
        return _json_error("Password must be at least 8 characters.", 400)
    if current_app.auth_ops.get_user_by_username(username):
        return _json_error("That username is already taken.", 400)

    current_app.auth_ops.create_local_user(username, password, role=role)
    return jsonify(ok=True), 201


@api_bp.route("/admin/users/pending-sso", methods=["POST"])
@login_required
@admin_required
def create_pending_sso_user():
    payload = _request_payload()
    username = _string_value(payload, "username").strip()
    role = _string_value(payload, "role", "user")

    if role not in VALID_ROLES:
        role = "user"
    if not username:
        return _json_error("Username is required.", 400)
    if current_app.auth_ops.get_user_by_username(username):
        return _json_error("That username is already taken.", 400)

    current_app.auth_ops.create_pending_oidc_user(username, role=role)
    return (
        jsonify(
            ok=True,
            message=(
                f"'{username}' is pre-authorized to sign in via SSO. "
                "The account activates automatically on their first login."
            ),
        ),
        201,
    )


@api_bp.route("/admin/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def update_user_role(user_id):
    payload = _request_payload()
    role = _string_value(payload, "role")
    if role not in VALID_ROLES:
        return _json_error("Invalid role.", 400)

    if user_id == current_user.id and role != "admin":
        if current_app.auth_ops.count_active_admins() <= 1:
            return _json_error("Cannot remove the last remaining admin.", 400)

    current_app.auth_ops.update_user_role(user_id, role)
    return jsonify(ok=True)


@api_bp.route("/admin/users/<int:user_id>/active", methods=["POST"])
@login_required
@admin_required
def toggle_user_active(user_id):
    payload = _request_payload()
    is_active = _bool_value(payload, "is_active")

    if user_id == current_user.id and not is_active:
        return _json_error("You cannot deactivate your own account.", 400)

    target = current_app.auth_ops.get_user_by_id(user_id)
    if (
        target
        and target["role"] == "admin"
        and not is_active
        and current_app.auth_ops.count_active_admins() <= 1
    ):
        return _json_error("Cannot deactivate the last remaining admin.", 400)

    current_app.auth_ops.set_user_active(user_id, is_active)
    return jsonify(ok=True)


@api_bp.route("/admin/users/<int:user_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        return _json_error("You cannot delete your own account.", 400)

    target = current_app.auth_ops.get_user_by_id(user_id)
    if (
        target
        and target["role"] == "admin"
        and current_app.auth_ops.count_active_admins() <= 1
    ):
        return _json_error("Cannot delete the last remaining admin.", 400)

    current_app.auth_ops.delete_user(user_id)
    return jsonify(ok=True)


@api_bp.route("/admin/sso")
@login_required
@admin_required
def sso():
    return jsonify(provider=current_app.auth_ops.get_oidc_provider(), roles=VALID_ROLES)


@api_bp.route("/admin/sso", methods=["POST"])
@login_required
@admin_required
def update_oidc():
    payload = _request_payload()
    name = _string_value(payload, "name", "OIDC Provider").strip() or "OIDC Provider"
    issuer = _string_value(payload, "issuer").strip()
    client_id = _string_value(payload, "client_id").strip()
    client_secret = _string_value(payload, "client_secret").strip()
    scopes = (
        _string_value(payload, "scopes", "openid profile email").strip()
        or "openid profile email"
    )
    default_role = _string_value(payload, "default_role", "user")
    enabled = _bool_value(payload, "enabled")
    disable_local_login = _bool_value(payload, "disable_local_login")
    auto_create_users = _bool_value(payload, "auto_create_users")

    if default_role not in VALID_ROLES:
        default_role = "user"

    existing = current_app.auth_ops.get_oidc_provider()
    if not client_secret and existing:
        client_secret = existing["client_secret"]

    if enabled and not (issuer and client_id and client_secret):
        return _json_error(
            "Issuer, client ID, and client secret are required to enable SSO.",
            400,
        )
    if disable_local_login and not enabled:
        return _json_error("SSO must be enabled to disable local login.", 400)

    current_app.auth_ops.save_oidc_provider(
        name=name,
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        enabled=enabled,
        default_role=default_role,
        disable_local_login=disable_local_login,
        auto_create_users=auto_create_users,
    )
    current_app.oidc_oauth.reload()
    return jsonify(ok=True)


@api_bp.route("/admin/brickset")
@login_required
@admin_required
def brickset():
    return jsonify(
        settings=current_app.db_ops.get_brickset_settings(),
        env_api_key_set=bool(current_app.config.get("BRICKSET_API_KEY")),
    )


@api_bp.route("/admin/brickset", methods=["POST"])
@login_required
@admin_required
def update_brickset():
    payload = _request_payload()
    api_key = _string_value(payload, "api_key").strip()
    username = _string_value(payload, "username").strip()
    password = _string_value(payload, "password").strip()

    existing = current_app.db_ops.get_brickset_settings()
    if not api_key and existing:
        api_key = existing["api_key"]
    if not password and existing:
        password = existing["password"]

    if not api_key:
        return _json_error("An API key is required.", 400)

    current_app.db_ops.save_brickset_settings(
        api_key=api_key,
        username=username,
        password=password,
    )
    current_app.brickset_api.configure(api_key)
    return jsonify(ok=True)


@api_bp.route("/admin/rebrickable")
@login_required
@admin_required
def rebrickable():
    return jsonify(
        settings=current_app.db_ops.get_rebrickable_settings(),
        env_api_key_set=bool(current_app.config.get("REBRICKABLE_API_KEY")),
    )


@api_bp.route("/admin/rebrickable", methods=["POST"])
@login_required
@admin_required
def update_rebrickable():
    payload = _request_payload()
    api_key = _string_value(payload, "api_key").strip()

    existing = current_app.db_ops.get_rebrickable_settings()
    if not api_key and existing:
        api_key = existing["api_key"]

    if not api_key:
        return _json_error("An API key is required.", 400)

    current_app.db_ops.save_rebrickable_settings(api_key=api_key)
    current_app.rebrickable_api.configure(api_key)
    return jsonify(ok=True)


@api_bp.route("/utility/labels")
@login_required
def labels():
    base_url = current_app.config["APP_BASE_URL"]
    sets_dir = current_app.config["SETS_DIR"]
    all_sets = current_app.db_ops.get_all_sets()

    if base_url:
        for set_data in all_sets:
            if not label_ops.label_exists(set_data, sets_dir):
                label_ops.generate_label(set_data, sets_dir, base_url)

    labeled_sets = [
        set_data for set_data in all_sets if label_ops.label_exists(set_data, sets_dir)
    ]
    return jsonify(
        sets=[_serialize_set(set_data) for set_data in labeled_sets],
        base_url_configured=bool(base_url),
    )


@api_bp.route("/utility/missing-metadata/run", methods=["POST"])
@login_required
def run_missing_metadata():
    results = current_app.db_ops.find_sets_missing_metadata()
    results_by_id = {result["setID"]: result for result in results}

    def _flag_missing(set_data, field):
        existing = results_by_id.get(set_data["setID"])
        if existing:
            existing["missing_fields"].append(field)
        else:
            set_data["missing_fields"] = [field]
            results.append(set_data)
            results_by_id[set_data["setID"]] = set_data

    base_url = current_app.config["APP_BASE_URL"]
    rebrickable_configured = bool(current_app.rebrickable_api.api_key)

    if base_url or rebrickable_configured:
        sets_dir = current_app.config["SETS_DIR"]
        for set_data in current_app.db_ops.get_all_sets():
            if base_url and not label_ops.label_exists(set_data, sets_dir):
                _flag_missing(set_data, "label")
            if rebrickable_configured and not set_data.get("parts_synced_at"):
                _flag_missing(set_data, "parts")
                _flag_missing(set_data, "minifigs")
        results.sort(key=lambda set_data: (set_data["name"] or "").lower())

    return jsonify(
        results=[
            {
                **_serialize_set(set_data),
                "missing_fields": set_data.get("missing_fields") or [],
            }
            for set_data in results
        ],
        base_url_configured=bool(base_url),
        rebrickable_configured=rebrickable_configured,
    )
