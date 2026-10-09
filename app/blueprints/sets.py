import os

from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    request,
    send_from_directory,
)
from flask_login import login_required
from werkzeug.utils import safe_join, secure_filename

from app import label_ops

sets_bp = Blueprint("sets", __name__)

# NOTE: this blueprint used to hold the full legacy Jinja UI (set list,
# wishlist, search, add/edit/delete, etc.). That UI has been fully replaced
# by the React SPA (see app/blueprints/spa.py) backed by the JSON API (see
# app/blueprints/api.py). Only the routes below remain, because they are
# still genuinely load-bearing: api.py's _serialize_set() builds URLs via
# url_for() against these exact endpoints to let the browser fetch images,
# instructions, and labels directly from Flask.


@sets_bp.route("/set/<int(signed=True):set_id>/label")
@login_required
def set_label(set_id):
    """Print-friendly view of a set's storage-box label."""
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        abort(404)
    if not label_ops.label_exists(set_data, current_app.config["SETS_DIR"]):
        abort(404)
    return render_template("set_label.html", set=set_data)


@sets_bp.route("/set/<int(signed=True):set_id>/label/image")
@login_required
def set_label_image(set_id):
    """Serves the generated label PNG itself (used by the label view page
    and the React set-detail page's "Print label" action)."""
    set_data = current_app.db_ops.get_set_by_id(set_id)
    if not set_data:
        abort(404)
    abs_path = label_ops.get_label_abs_path(set_data, current_app.config["SETS_DIR"])
    if not os.path.isfile(abs_path):
        abort(404)
    directory, filename = os.path.split(abs_path)
    safe_set_number = secure_filename(str(set_data["setNumber"]))
    download_name = f"label-{safe_set_number}.png"
    return send_from_directory(
        directory,
        filename,
        download_name=download_name if request.args.get("download") else None,
    )


@sets_bp.route("/files/sets/<path:filename>")
@login_required
def custom_static(filename):
    """Serve downloaded images/instructions, guarding against path traversal.

    Deliberately NOT at a bare /sets/<path:filename> prefix: the React SPA now
    owns /sets and /sets/<id> as client-side routes at the site root, and
    Werkzeug's routing would otherwise swallow a direct navigation/refresh to
    e.g. /sets/42 into this file-serving view instead of the SPA."""
    sets_dir = current_app.config["SETS_DIR"]
    safe_path = safe_join(sets_dir, filename)
    if safe_path is None:
        abort(404)
    return send_from_directory(sets_dir, filename)
