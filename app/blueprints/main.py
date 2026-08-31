from flask import Blueprint, redirect, url_for
from flask_login import login_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def index():
    # There's no standalone home page — "My Sets" is the default landing page.
    return redirect(url_for("sets.list_sets"))
