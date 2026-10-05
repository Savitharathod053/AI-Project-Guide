"""
FACULTY MONITORING ROUTES FOR PROJEXA
=====================================
Faculty dashboard, multi-criteria project filtering, detailed risk review,
and faculty feedback & scoring submission.
"""

import json
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models import db, Project, ProjectProgress, Prediction, FacultyFeedback, EarlyWarningAlert
from app.services.feature_engineering import compute_derived_features

faculty_bp = Blueprint("faculty", __name__)


def faculty_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_faculty:
            flash("Access restricted to faculty advisors.", "warning")
            return redirect(url_for("student.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


@faculty_bp.route("/dashboard")
@faculty_required
def dashboard():
    # Filter parameters
    risk_filter = request.args.get("risk", "ALL").upper()
    domain_filter = request.args.get("domain", "ALL")
    search_query = request.args.get("q", "").strip()
    sort_by = request.args.get("sort", "risk_desc")

    # Fetch all projects
    query = Project.query

    if search_query:
        query = query.filter(
            (Project.project_name.ilike(f"%{search_query}%")) |
            (Project.technologies.ilike(f"%{search_query}%"))
        )

    if domain_filter != "ALL":
        query = query.filter(Project.domain == domain_filter)

    all_projects = query.all()

    # Calculate overall risk statistics
    total_projects = len(all_projects)
    low_count = 0
    mod_count = 0
    high_count = 0
    crit_count = 0

    project_items = []
    for p in all_projects:
        pred = p.latest_prediction
        prog = p.latest_progress
        risk_lvl = pred.risk_level if pred else "NOT ASSESSED"
        fail_prob = pred.failure_probability if pred else 0.0

        if risk_lvl == "LOW":
            low_count += 1
        elif risk_lvl == "MODERATE":
            mod_count += 1
        elif risk_lvl == "HIGH":
            high_count += 1
        elif risk_lvl == "CRITICAL":
            crit_count += 1

        # Apply risk filter
        if risk_filter != "ALL" and risk_lvl != risk_filter:
            continue

        project_items.append({
            "project": p,
            "progress": prog,
            "prediction": pred,
            "risk_level": risk_lvl,
            "failure_probability": fail_prob,
            "success_probability": pred.success_probability if pred else 0.0,
            "progress_percentage": prog.progress_percentage if prog else 0.0,
            "student_name": p.owner.name if p.owner else "Unknown",
            "department": p.owner.department if p.owner else ""
        })

    # Sorting
    if sort_by == "risk_desc":
        project_items.sort(key=lambda x: x["failure_probability"], reverse=True)
    elif sort_by == "risk_asc":
        project_items.sort(key=lambda x: x["failure_probability"])
    elif sort_by == "progress_asc":
        project_items.sort(key=lambda x: x["progress_percentage"])
    elif sort_by == "progress_desc":
        project_items.sort(key=lambda x: x["progress_percentage"], reverse=True)
    elif sort_by == "deadline_asc":
        project_items.sort(key=lambda x: x["project"].deadline)

    # Active unread alerts across monitored projects
    alerts = EarlyWarningAlert.query.order_by(EarlyWarningAlert.created_at.desc()).limit(10).all()

    stats = {
        "total": total_projects,
        "low": low_count,
        "moderate": mod_count,
        "high": high_count,
        "critical": crit_count
    }

    domains = [
        "Web Development", "Mobile Applications", "Machine Learning & AI",
        "Internet of Things (IoT)", "Cloud Computing", "Cybersecurity", "Blockchain"
    ]

    return render_template(
        "faculty/dashboard.html",
        stats=stats,
        project_items=project_items,
        alerts=alerts,
        risk_filter=risk_filter,
        domain_filter=domain_filter,
        search_query=search_query,
        sort_by=sort_by,
        domains=domains
    )


@faculty_bp.route("/projects/<int:project_id>")
@faculty_required
def project_view(project_id: int):
    project = Project.query.get_or_404(project_id)
    latest_progress = project.latest_progress
    latest_prediction = project.latest_prediction

    # Derived indicators
    derived = {}
    if latest_progress:
        derived = compute_derived_features(
            total_tasks=latest_progress.total_tasks,
            completed_tasks=latest_progress.completed_tasks,
            delayed_tasks=latest_progress.delayed_tasks,
            progress_percentage=latest_progress.progress_percentage,
            testing_percentage=latest_progress.testing_percentage,
            documentation_percentage=latest_progress.documentation_percentage,
            bugs=latest_progress.bugs,
            start_date=project.start_date,
            deadline=project.deadline
        )

    # History list for Chart.js
    predictions_history = Prediction.query.filter_by(project_id=project.id).order_by(Prediction.created_at.asc()).all()
    history_data = [
        {
            "date": p.created_at.strftime("%b %d"),
            "failure_probability": p.failure_probability,
            "success_probability": p.success_probability,
            "risk_level": p.risk_level
        }
        for p in predictions_history
    ]

    feedback_list = project.feedback_records.all()
    recommendations = latest_prediction.recommendations.all() if latest_prediction else []

    return render_template(
        "faculty/project_view.html",
        project=project,
        progress=latest_progress,
        prediction=latest_prediction,
        derived=derived,
        history_json=json.dumps(history_data),
        feedback_list=feedback_list,
        recommendations=recommendations,
        shap_list=latest_prediction.get_shap_list() if latest_prediction else [],
        risk_factors=latest_prediction.get_risk_factors() if latest_prediction else []
    )


@faculty_bp.route("/projects/<int:project_id>/feedback", methods=["POST"])
@faculty_required
def submit_feedback(project_id: int):
    project = Project.query.get_or_404(project_id)
    score_str = request.form.get("score")
    feedback_text = request.form.get("feedback", "").strip()
    milestone_approved = bool(request.form.get("milestone_approved"))

    if not feedback_text:
        flash("Feedback comments cannot be empty.", "danger")
        return redirect(url_for("faculty.project_view", project_id=project.id))

    score = float(score_str) if score_str else None

    fb = FacultyFeedback(
        project_id=project.id,
        faculty_id=current_user.id,
        score=score,
        feedback=feedback_text,
        milestone_approved=milestone_approved
    )
    db.session.add(fb)

    # If score is given, optionally update latest progress evaluation score
    if score is not None and project.latest_progress:
        project.latest_progress.evaluation_score = score

    db.session.commit()
    flash("Faculty review and feedback posted successfully.", "success")
    return redirect(url_for("faculty.project_view", project_id=project.id))
