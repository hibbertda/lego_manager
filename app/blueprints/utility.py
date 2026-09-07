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


@utility_bp.route("/missing-metadata")
@login_required
def missing_metadata():
    """Manual maintenance page: scans on demand (via the Run button) for sets
    missing a year, theme, piece count, cover image, instructions, or (if
    APP_BASE_URL is configured) a storage-box label."""
    return render_template("utility_missing_metadata.html", ran=False, results=None)


@utility_bp.route("/missing-metadata/run", methods=["POST"])
@login_required
def run_missing_metadata():
    results = current_app.db_ops.find_sets_missing_metadata()
    base_url = current_app.config["APP_BASE_URL"]
    if base_url:
        # Labels are only ever generated once a base URL is configured (see
        # app/label_ops.py), so flagging them as "missing" when it's unset
        # would just be noise a user can't act on yet.
        sets_dir = current_app.config["SETS_DIR"]
        results_by_id = {r["setID"]: r for r in results}
        for set_data in current_app.db_ops.get_all_sets():
            if label_ops.label_exists(set_data, sets_dir):
                continue
            existing = results_by_id.get(set_data["setID"])
            if existing:
                existing["missing_fields"].append("label")
            else:
                set_data["missing_fields"] = ["label"]
                results.append(set_data)
                results_by_id[set_data["setID"]] = set_data
        results.sort(key=lambda s: (s["name"] or "").lower())

    return render_template("utility_missing_metadata.html", ran=True, results=results)

