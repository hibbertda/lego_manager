import os
import shutil

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import login_required
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import safe_join, secure_filename

from app.decorators import admin_required
from app.sql_ops import DEFAULT_SORT, SORT_LABELS, VALID_BUILD_STATUSES

sets_bp = Blueprint("sets", __name__)

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ALLOWED_INSTRUCTION_EXTENSIONS = {".pdf"}
# Pillow's format name for each allowed image extension, used to verify the
# uploaded bytes actually decode as the type of image they claim to be
# (extension alone is trivially spoofable and was flagged in the security
# review as a residual content-sniffing / stored-content risk).
_PILLOW_FORMATS_BY_EXT = {
    ".png": {"PNG"},
    ".jpg": {"JPEG"},
    ".jpeg": {"JPEG"},
    ".gif": {"GIF"},
    ".webp": {"WEBP"},
}


def _has_allowed_extension(filename: str, allowed: set) -> bool:
    return os.path.splitext(filename)[1].lower() in allowed


def _is_valid_image(file_storage, ext: str) -> bool:
    """Verify the uploaded file's actual bytes decode as an image matching its
    extension, not just that the filename looks right."""
    try:
        file_storage.stream.seek(0)
        with Image.open(file_storage.stream) as img:
            img.verify()
        # verify() closes/invalidates the parser; re-open to check the format,
        # since Image.verify() doesn't guarantee `img.format` is still valid.
        file_storage.stream.seek(0)
        with Image.open(file_storage.stream) as img:
            fmt = img.format
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    finally:
        file_storage.stream.seek(0)
    return fmt in _PILLOW_FORMATS_BY_EXT.get(ext, set())


def _is_valid_pdf(file_storage) -> bool:
    """Cheap magic-byte check: real PDFs start with the '%PDF-' header."""
    try:
        file_storage.stream.seek(0)
        header = file_storage.stream.read(5)
    finally:
        file_storage.stream.seek(0)
    return header == b"%PDF-"


@sets_bp.route("/add_set", methods=["GET", "POST"])
@login_required
def add_set():
    if request.method == "GET":
        # Adding a set is now handled by the "Add a Set" modal available on
        # every page (see base.html) rather than a dedicated page.
        return redirect(url_for("sets.list_sets"))

    set_number = request.form["set_number"].strip()
    if not set_number:
        flash("Set number is required.", "error")
        return redirect(url_for("sets.list_sets"))

    combined_data = current_app.brickset_api.get_combined_data(
        set_number,
        base_dir=current_app.config["SETS_DIR"],
        max_bytes=current_app.config["MAX_DOWNLOAD_BYTES"],
    )
    if combined_data:
        current_app.db_ops.insert_combined_data(combined_data)
        return redirect(url_for("sets.list_sets"))
    flash(
        "Failed to retrieve set data from Brickset. Check the set number, "
        "your Brickset API key, or add the set manually instead.",
        "error",
    )
    return redirect(url_for("sets.list_sets"))


@sets_bp.route("/add_set/manual", methods=["POST"])
@login_required
def add_set_manual():
    set_number = request.form.get("set_number", "").strip()
    name = request.form.get("name", "").strip()
    year = request.form.get("year", type=int)
    theme = request.form.get("theme", "").strip() or None
    pieces = request.form.get("pieces", type=int)

    if not set_number or not name:
        flash("Set number and name are required.", "error")
        return redirect(url_for("sets.list_sets"))

    safe_set_number = secure_filename(set_number)
    if not safe_set_number:
        flash("Set number contains only invalid characters.", "error")
        return redirect(url_for("sets.list_sets"))

    sets_dir = current_app.config["SETS_DIR"]
    # Store paths relative to SETS_DIR (consistent with the Brickset-sourced
    # flow), so sets.custom_static can serve them the same way either way.
    rel_images_dir = os.path.join(safe_set_number, "images")
    rel_instructions_dir = os.path.join(safe_set_number, "instructions")

    local_images = []
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        ext = os.path.splitext(image_file.filename)[1].lower()
        if not _has_allowed_extension(image_file.filename, ALLOWED_IMAGE_EXTENSIONS):
            flash("Image must be a PNG, JPG, GIF, or WEBP file.", "error")
            return redirect(url_for("sets.list_sets"))
        if not _is_valid_image(image_file, ext):
            flash("Image file is corrupt or is not a valid image.", "error")
            return redirect(url_for("sets.list_sets"))
        filename = secure_filename(image_file.filename)
        if not filename:
            flash("Image filename is invalid.", "error")
            return redirect(url_for("sets.list_sets"))
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
                flash("Instructions must be PDF files.", "error")
                return redirect(url_for("sets.list_sets"))
            if not _is_valid_pdf(pdf_file):
                flash("Instructions file is not a valid PDF.", "error")
                return redirect(url_for("sets.list_sets"))
            filename = secure_filename(pdf_file.filename)
            if not filename:
                flash("Instructions filename is invalid.", "error")
                return redirect(url_for("sets.list_sets"))
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
    flash("Set added manually.", "success")
    return redirect(url_for("sets.set_detail", set_id=set_id))


@sets_bp.route("/set/<int(signed=True):set_id>")
@login_required
def set_detail(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        abort(404)
    return render_template("set_detail.html", set=set_data)


@sets_bp.route("/set/<int(signed=True):set_id>/progress", methods=["POST"])
@login_required
def update_progress(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        abort(404)

    build_page = request.form.get("build_page", 0, type=int)
    build_status = request.form.get("build_status", "not_started")
    if build_status not in VALID_BUILD_STATUSES:
        return "Invalid build status", 400

    current_app.db_ops.update_build_progress(set_id, max(0, build_page), build_status)
    return redirect(url_for("sets.set_detail", set_id=set_id))


@sets_bp.route("/set/<int(signed=True):set_id>/progress/page", methods=["POST"])
@login_required
def update_progress_page(set_id):
    """AJAX endpoint used by the PDF viewer to auto-save the current page as the
    user reads instructions, without disturbing the manually-set build_status
    (unless it's still 'not_started', which gets bumped to 'in_progress')."""
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        abort(404)

    payload = request.get_json(silent=True) or {}
    build_page = payload.get("build_page", 0)
    if not isinstance(build_page, int):
        return jsonify(error="build_page must be an integer"), 400

    current_app.db_ops.update_build_page(set_id, max(0, build_page))
    return jsonify(ok=True, build_page=max(0, build_page))


@sets_bp.route("/set/<int(signed=True):set_id>/status", methods=["POST"])
@login_required
def update_status_only(set_id):
    """AJAX endpoint for the quick build-status dropdown on set list/grid
    cards, so users can change status without opening the set detail page."""
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        abort(404)

    payload = request.get_json(silent=True) or {}
    build_status = payload.get("build_status")
    if build_status not in VALID_BUILD_STATUSES:
        return jsonify(error="Invalid build status"), 400

    current_app.db_ops.update_build_status_only(set_id, build_status)
    return jsonify(ok=True, build_status=build_status)


@sets_bp.route("/set/<int(signed=True):set_id>/favorite", methods=["POST"])
@login_required
def toggle_favorite(set_id):
    """AJAX endpoint for the heart button on set list/grid cards."""
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        abort(404)

    favorite = current_app.db_ops.toggle_favorite(set_id)
    return jsonify(ok=True, favorite=favorite)


@sets_bp.route("/set/<int(signed=True):set_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_set(set_id):
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        abort(404)

    deleted = current_app.db_ops.delete_set(set_id)
    if deleted:
        set_dir = os.path.join(
            current_app.config["SETS_DIR"], str(set_data["setNumber"])
        )
        if os.path.isdir(set_dir):
            shutil.rmtree(set_dir, ignore_errors=True)

    return redirect(url_for("sets.list_sets"))


@sets_bp.route("/search")
@login_required
def search():
    query = request.args.get("query", "")
    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = current_app.config["SETS_PER_PAGE"]
    sets_data, total = current_app.db_ops.search_sets(
        query, page=page, per_page=per_page
    )
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "search_results.html",
        sets=sets_data,
        query=query,
        page=page,
        total_pages=total_pages,
    )


@sets_bp.route("/search/suggest")
@login_required
def search_suggest():
    """JSON predictive-search endpoint used by the top bar's live search box."""
    query = request.args.get("query", "").strip()
    if not query:
        return {"results": []}

    sets_data, total = current_app.db_ops.search_sets(query, page=1, per_page=8)
    results = [
        {
            "id": s["setID"],
            "name": s["name"],
            "setNumber": s["setNumber"],
            "year": s["year"],
            "theme": s["theme"],
            "image": (
                url_for("sets.custom_static", filename=s["local_images"][0])
                if s.get("local_images")
                else None
            ),
            "url": url_for("sets.set_detail", set_id=s["setID"]),
        }
        for s in sets_data
    ]
    return {"results": results, "total": total}


@sets_bp.route("/setlist")
@login_required
def list_sets():
    page = max(1, request.args.get("page", 1, type=int) or 1)
    view = request.args.get("view", "grid")
    if view not in ("list", "grid"):
        view = "grid"
    theme = request.args.get("theme") or None
    build_status = request.args.get("status") or None
    if build_status not in VALID_BUILD_STATUSES:
        build_status = None
    favorite_only = request.args.get("favorite") == "1"
    sort = request.args.get("sort") or DEFAULT_SORT
    if sort not in SORT_LABELS:
        sort = DEFAULT_SORT
    per_page = current_app.config["SETS_PER_PAGE"]
    sets_data, total = current_app.db_ops.list_sets(
        page=page,
        per_page=per_page,
        theme=theme,
        build_status=build_status,
        favorite_only=favorite_only,
        sort=sort,
    )
    total_pages = max(1, (total + per_page - 1) // per_page)
    themes = current_app.db_ops.get_distinct_themes()
    return render_template(
        "sets.html",
        sets=sets_data,
        page=page,
        total_pages=total_pages,
        view=view,
        theme=theme,
        status=build_status,
        favorite_only=favorite_only,
        themes=themes,
        sort=sort,
        sort_labels=SORT_LABELS,
    )


@sets_bp.route("/sets/<path:filename>")
@login_required
def custom_static(filename):
    """Serve downloaded images/instructions, guarding against path traversal."""
    sets_dir = current_app.config["SETS_DIR"]
    safe_path = safe_join(sets_dir, filename)
    if safe_path is None:
        abort(404)
    return send_from_directory(sets_dir, filename)
