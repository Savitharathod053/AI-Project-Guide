"""
AUTHENTICATION AND USER MANAGEMENT ROUTES
=========================================
Handles secure registration, password hashing, login, logout, and profile updates.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "student").strip().lower()
        department = request.form.get("department", "Computer Science & Engineering").strip()

        # Validation
        if not name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("auth/register.html")

        if role not in ["student", "faculty"]:
            role = "student"

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with this email address already exists. Please sign in.", "warning")
            return redirect(url_for("auth.login"))

        user = User(
            name=name,
            email=email,
            role=role,
            department=department
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"Welcome to ProjectGuard, {user.name}! Your account has been created.", "success")
        
        if user.is_student:
            return redirect(url_for("student.dashboard"))
        else:
            return redirect(url_for("faculty.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_student:
            return redirect(url_for("student.dashboard"))
        return redirect(url_for("faculty.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.name}!", "success")
            next_page = request.args.get("next")
            if next_page and not next_page.startswith("//"):
                return redirect(next_page)
            if user.is_student:
                return redirect(url_for("student.dashboard"))
            else:
                return redirect(url_for("faculty.dashboard"))
        else:
            flash("Invalid email or password. Please try again.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "update_profile":
            current_user.name = request.form.get("name", current_user.name).strip()
            current_user.department = request.form.get("department", current_user.department).strip()
            db.session.commit()
            flash("Profile updated successfully.", "success")
            
        elif action == "change_password":
            current_pwd = request.form.get("current_password", "")
            new_pwd = request.form.get("new_password", "")
            confirm_pwd = request.form.get("confirm_new_password", "")
            
            if not current_user.check_password(current_pwd):
                flash("Current password is incorrect.", "danger")
            elif new_pwd != confirm_pwd:
                flash("New passwords do not match.", "danger")
            elif len(new_pwd) < 6:
                flash("New password must be at least 6 characters.", "danger")
            else:
                current_user.set_password(new_pwd)
                db.session.commit()
                flash("Password changed successfully.", "success")

    return render_template("auth/profile.html")
