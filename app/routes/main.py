"""
MAIN / PUBLIC ROUTES FOR PROJECTGUARD
=====================================
Landing page, feature showcase, FAQ, and methodology disclaimers.
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_student:
            return redirect(url_for("student.dashboard"))
        elif current_user.is_faculty:
            return redirect(url_for("faculty.dashboard"))
    return render_template("index.html")


@main_bp.route("/about")
def about():
    return render_template("about.html")
