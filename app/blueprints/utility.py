from flask import Blueprint, current_app, redirect, render_template, url_for
from flask_login import login_required

from app import label_ops

utility_bp = Blueprint("utility", __name__, url_prefix="/utility")


@utility_bp.route("/")
@login_required
def index():
    return redirect(url_for("utility.labels"))


@utility_bp.route("/labels")
@login_required
def labels():
    """Lists every set that has a generated storage-box label, with links to
    view/print or download each one. If APP_BASE_URL isn't configured, no
    labels can be generated (see app/label_ops.py), so this page shows a
    warning instead of silently listing nothing."""
    base_url = current_app.config["APP_BASE_URL"]
    sets_dir = current_app.config["SETS_DIR"]
    all_sets = current_app.db_ops.get_all_sets()

    if base_url:
        # Self-heal: generate labels on the fly for any set that doesn't
        # have one yet (e.g. sets added before this feature existed, or
        # before APP_BASE_URL was configured), so this page always reflects
        # the full collection without needing a separate migration step.
        for set_data in all_sets:
            if not label_ops.label_exists(set_data, sets_dir):
                label_ops.generate_label(set_data, sets_dir, base_url)

    labeled_sets = [s for s in all_sets if label_ops.label_exists(s, sets_dir)]
    return render_template(
        "utility_labels.html",
        sets=labeled_sets,
        base_url_configured=bool(base_url),
    )
