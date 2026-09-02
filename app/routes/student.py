"""
STUDENT & AI MENTOR ROUTES FOR PROJECTGUARD
===========================================
Handles simple title+description project creation, AI task generation,
task review, interactive task board, AI mentor chat, smart check-ins,
and risk analytics.
"""

import json
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app.models import (
    db, Project, Task, ProjectProgress, Prediction, Recommendation,
    ProjectCheckin, AIMentorMessage, FacultyFeedback, EarlyWarningAlert
)
from app.services.ai_service import get_ai_service
from app.services.health_service import calculate_project_health_score
from app.services.feature_engineering import prepare_feature_row, compute_derived_features
from app.services.ml_service import get_ml_service
from app.services.recommendation_engine import generate_recommendations
from app.services.alert_service import check_and_create_early_warning

student_bp = Blueprint("student", __name__)


def student_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_student:
            flash("Access restricted to student accounts.", "warning")
            return redirect(url_for("faculty.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def get_student_project_or_404(project_id: int) -> Project:
    project = Project.query.filter_by(id=project_id, owner_id=current_user.id).first()
    if not project:
        abort(404)
    return project


@student_bp.route("/dashboard")
@student_required
def dashboard():
    projects = Project.query.filter_by(owner_id=current_user.id).order_by(Project.updated_at.desc()).all()
    
    total_projects = len(projects)
    low_risk_count = 0
    mod_risk_count = 0
    high_risk_count = 0
    crit_risk_count = 0
    
    project_cards = []
    for p in projects:
        pred = p.latest_prediction
        prog = p.latest_progress
        tasks = p.tasks.all()
        health_info = calculate_project_health_score(p, tasks)
        
        risk_level = pred.risk_level if pred else "LOW"
        fail_prob = pred.failure_probability if pred else 15.0
        succ_prob = pred.success_probability if pred else 85.0
        
        if risk_level == "LOW":
            low_risk_count += 1
        elif risk_level == "MODERATE":
            mod_risk_count += 1
        elif risk_level == "HIGH":
            high_risk_count += 1
        elif risk_level == "CRITICAL":
            crit_risk_count += 1

        # Check risk delta
        preds_list = p.predictions.limit(2).all()
        risk_delta = None
        if len(preds_list) >= 2:
            risk_delta = round(preds_list[0].failure_probability - preds_list[1].failure_probability, 1)

        project_cards.append({
            "project": p,
            "latest_progress": prog,
            "latest_prediction": pred,
            "health_score": health_info["health_score"],
            "total_tasks": len(tasks),
            "completed_tasks": p.completed_tasks_count,
            "blocked_tasks": p.blocked_tasks_count,
            "risk_level": risk_level,
            "failure_probability": fail_prob,
            "success_probability": succ_prob,
            "risk_delta": risk_delta,
            "days_remaining": health_info["days_remaining"]
        })

    # Unread alerts
    project_ids = [p.id for p in projects]
    unread_alerts = EarlyWarningAlert.query.filter(
        EarlyWarningAlert.project_id.in_(project_ids) if project_ids else False,
        EarlyWarningAlert.is_read == False
    ).order_by(EarlyWarningAlert.created_at.desc()).all()

    stats = {
        "total": total_projects,
        "low": low_risk_count,
        "moderate": mod_risk_count,
        "high": high_risk_count,
        "critical": crit_risk_count
    }

    return render_template(
        "student/dashboard.html",
        stats=stats,
        project_cards=project_cards,
        alerts=unread_alerts
    )


@student_bp.route("/projects/new", methods=["GET", "POST"])
@student_required
def create_project():
    """
    Step 1 of Project Creation: Student provides ONLY Project Title and Description.
    AI generates the complete task plan.
    """
    if request.method == "POST":
        project_name = request.form.get("project_name", "").strip()
        description = request.form.get("description", "").strip()
        deadline_str = request.form.get("deadline")

        if not project_name or not description:
            flash("Please provide a project title and description.", "danger")
            return render_template("student/project_create_ai.html")

        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                deadline = date.today() + timedelta(days=90)
        else:
            deadline = date.today() + timedelta(days=90)

        # 1. AI Analysis & Task Generation
        ai_service = get_ai_service()
        ai_plan = ai_service.analyze_project_and_generate_tasks(project_name, description)

        # 2. Create Project Record
        project = Project(
            owner_id=current_user.id,
            project_name=project_name,
            description=description,
            objective=ai_plan.get("main_objective", "Deliver a fully working academic project."),
            project_summary=ai_plan.get("project_summary", ""),
            domain=ai_plan.get("domain", "Web Development"),
            project_type=ai_plan.get("project_type", "Capstone Project"),
            technology_difficulty=ai_plan.get("technology_difficulty", "Medium"),
            technologies=", ".join(ai_plan.get("suggested_technologies", ["Python", "Flask", "PostgreSQL"])),
            technologies_count=len(ai_plan.get("suggested_technologies", [1, 2, 3])),
            start_date=date.today(),
            deadline=deadline
        )
        db.session.add(project)
        db.session.commit()

        # 3. Create Generated Core Tasks
        tasks_created = 0
        for item in ai_plan.get("core_tasks", []):
            task = Task(
                project_id=project.id,
                title=item["task_title"],
                description=item.get("description", ""),
                category=item.get("category", "Backend"),
                priority=item.get("priority", "High"),
                difficulty=item.get("estimated_difficulty", "Medium"),
                status="Not Started",
                is_core=True,
                is_optional=False,
                source="AI_GENERATED",
                reason=item.get("reason", ""),
                dependencies=json.dumps(item.get("dependencies", []))
            )
            db.session.add(task)
            tasks_created += 1

        # Optional tasks
        for item in ai_plan.get("optional_tasks", []):
            task = Task(
                project_id=project.id,
                title=item["task_title"],
                description=item.get("description", ""),
                category=item.get("category", "UI/UX"),
                priority="Optional",
                difficulty=item.get("estimated_difficulty", "Easy"),
                status="Optional",
                is_core=False,
                is_optional=True,
                source="AI_GENERATED",
                reason=item.get("reason", "")
            )
            db.session.add(task)
            tasks_created += 1

        project.initial_task_count = tasks_created
        db.session.commit()

        # 4. Sync Initial Progress & ML Risk Baseline
        _sync_project_metrics_and_predict(project)

        flash("AI has analyzed your project and generated your development plan! Review and adjust your tasks below.", "success")
        return redirect(url_for("student.review_tasks", project_id=project.id))

    return render_template("student/project_create_ai.html")


@student_bp.route("/projects/<int:project_id>/review-tasks")
@student_required
def review_tasks(project_id: int):
    """
    Step 2: Student reviews AI-generated tasks, can keep/edit/remove or add extra tasks.
    """
    project = get_student_project_or_404(project_id)
    tasks = project.tasks.all()
    core_tasks = [t for t in tasks if not t.is_optional]
    optional_tasks = [t for t in tasks if t.is_optional]

    return render_template(
        "student/task_review.html",
        project=project,
        core_tasks=core_tasks,
        optional_tasks=optional_tasks
    )


@student_bp.route("/projects/<int:project_id>")
@student_required
def project_detail(project_id: int):
    """
    Full Project Dashboard with 6 Tabs: Overview, Tasks, AI Mentor, Risk Analysis, What-If, Timeline.
    """
    project = get_student_project_or_404(project_id)
    tasks = project.tasks.all()
    latest_progress = project.latest_progress
    latest_prediction = project.latest_prediction
    
    # Calculate health score & indicators
    health_info = calculate_project_health_score(project, tasks)
    project.health_score = health_info["health_score"]
    db.session.commit()

    derived = compute_derived_features(
        total_tasks=len(tasks),
        completed_tasks=project.completed_tasks_count,
        delayed_tasks=latest_progress.delayed_tasks if latest_progress else 0,
        progress_percentage=project.calculated_progress_pct,
        testing_percentage=latest_progress.testing_percentage if latest_progress else 0.0,
        documentation_percentage=latest_progress.documentation_percentage if latest_progress else 0.0,
        bugs=latest_progress.bugs if latest_progress else 0,
        start_date=project.start_date,
        deadline=project.deadline
    )

    # Risk history for Chart.js
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

    checkins = project.checkins.limit(5).all()
    chat_messages = project.chat_messages.limit(20).all()
    recommendations = latest_prediction.recommendations.all() if latest_prediction else []
    feedback_list = project.feedback_records.all()
    alerts = project.alerts.all()

    return render_template(
        "student/project_detail.html",
        project=project,
        tasks=tasks,
        progress=latest_progress,
        prediction=latest_prediction,
        health_info=health_info,
        derived=derived,
        history_json=json.dumps(history_data),
        checkins=checkins,
        chat_messages=chat_messages,
        recommendations=recommendations,
        feedback_list=feedback_list,
        alerts=alerts
    )


@student_bp.route("/projects/<int:project_id>/tasks/add", methods=["POST"])
@student_required
def add_task(project_id: int):
    project = get_student_project_or_404(project_id)
    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title cannot be empty.", "warning")
        return redirect(url_for("student.project_detail", project_id=project.id, _anchor="tasks-tab"))

    # Evaluate task with AI for duplicate detection and categorization
    ai_service = get_ai_service()
    eval_res = ai_service.evaluate_additional_task(project, title, project.tasks.all())

    task = Task(
        project_id=project.id,
        title=eval_res["title"],
        description=request.form.get("description", "").strip() or eval_res["message"],
        category=request.form.get("category", eval_res["category"]),
        priority=request.form.get("priority", eval_res["priority"]),
        difficulty=request.form.get("difficulty", "Medium"),
        status="Not Started",
        is_core=bool(request.form.get("is_core", True)),
        is_optional=not bool(request.form.get("is_core", True)),
        source="STUDENT_ADDED"
    )
    db.session.add(task)
    db.session.commit()

    _sync_project_metrics_and_predict(project)

    if eval_res["is_duplicate"]:
        flash(f"⚠️ Notice: '{title}' appears similar to existing task '{eval_res['duplicate_of']}', but was added as requested.", "info")
    else:
        flash(f"Task '{title}' added to your project plan.", "success")

    return redirect(url_for("student.project_detail", project_id=project.id, _anchor="tasks-tab"))


@student_bp.route("/projects/<int:project_id>/tasks/<int:task_id>/status", methods=["POST"])
@student_required
def update_task_status(project_id: int, task_id: int):
    project = get_student_project_or_404(project_id)
    task = Task.query.filter_by(id=task_id, project_id=project.id).first_or_404()
    
    new_status = request.form.get("status", "Completed")
    blocker_note = request.form.get("blocker_reason", "").strip()

    task.status = new_status
    if new_status == "Blocked" and blocker_note:
        task.blocker_reason = blocker_note
    db.session.commit()

    # Re-sync progress and re-run ML risk assessment
    _sync_project_metrics_and_predict(project)

    # Provide AI Blocker assistance if blocked
    if new_status == "Blocked" and blocker_note:
        ai_service = get_ai_service()
        guidance = ai_service.troubleshoot_blocker(task.title, blocker_note)
        # Post AI mentor reply
        db.session.add(AIMentorMessage(
            project_id=project.id,
            user_id=current_user.id,
            role="assistant",
            message=f"I noticed you marked **'{task.title}'** as Blocked ({blocker_note}). Here is guidance to resolve it:\n\n{guidance}"
        ))
        db.session.commit()
        flash(f"Task marked as Blocked. AI Mentor has posted troubleshooting advice in the AI Mentor tab!", "warning")
    else:
        flash(f"Task '{task.title}' marked as {new_status}.", "success")

    return redirect(url_for("student.project_detail", project_id=project.id, _anchor="tasks-tab"))


@student_bp.route("/projects/<int:project_id>/tasks/<int:task_id>/delete", methods=["POST"])
@student_required
def delete_task(project_id: int, task_id: int):
    project = get_student_project_or_404(project_id)
    task = Task.query.filter_by(id=task_id, project_id=project.id).first_or_404()
    title = task.title
    db.session.delete(task)
    db.session.commit()
    _sync_project_metrics_and_predict(project)
    flash(f"Task '{title}' removed.", "info")
    return redirect(url_for("student.project_detail", project_id=project.id, _anchor="tasks-tab"))


@student_bp.route("/projects/<int:project_id>/check-in", methods=["POST"])
@student_required
def run_checkin(project_id: int):
    """
    Runs AI Smart Check-In: Analyzes task progress, timeline lag, blockers,
    computes transparent Health Score, and logs checkin record.
    """
    project = get_student_project_or_404(project_id)
    tasks = project.tasks.all()
    health_info = calculate_project_health_score(project, tasks)
    
    ai_service = get_ai_service()
    checkin_res = ai_service.run_ai_project_checkin(project, tasks, health_info["days_remaining"])

    checkin = ProjectCheckin(
        project_id=project.id,
        health_score=health_info["health_score"],
        risk_level=project.latest_prediction.risk_level if project.latest_prediction else "LOW",
        ai_summary=checkin_res["ai_summary"],
        recommendations_json=json.dumps(checkin_res["recommendations"]),
        task_completion_score=health_info["task_completion"],
        schedule_score=health_info["schedule"],
        testing_score=health_info["testing"],
        doc_score=health_info["documentation"],
        blocked_score=health_info["blocked_tasks"],
        core_score=health_info["core_functionality"],
        notes=request.form.get("notes", "")
    )
    db.session.add(checkin)
    project.health_score = health_info["health_score"]
    db.session.commit()

    flash("AI Smart Check-In completed! Health score and recommended next steps updated.", "success")
    return redirect(url_for("student.project_detail", project_id=project.id, _anchor="mentor-tab"))


@student_bp.route("/projects/<int:project_id>/mentor-chat", methods=["POST"])
@student_required
def mentor_chat(project_id: int):
    """Context-aware AI Mentor Chat conversation."""
    project = get_student_project_or_404(project_id)
    question = request.form.get("message", "").strip()
    if not question:
        return redirect(url_for("student.project_detail", project_id=project.id, _anchor="mentor-tab"))

    # Save user message
    user_msg = AIMentorMessage(
        project_id=project.id,
        user_id=current_user.id,
        role="user",
        message=question
    )
    db.session.add(user_msg)
    db.session.commit()

    # Generate contextual answer
    tasks = project.tasks.all()
    health_info = calculate_project_health_score(project, tasks)
    ai_service = get_ai_service()
    answer = ai_service.answer_mentor_question(project, question, tasks, health_info["days_remaining"])

    # Save assistant message
    ai_msg = AIMentorMessage(
        project_id=project.id,
        user_id=current_user.id,
        role="assistant",
        message=answer
    )
    db.session.add(ai_msg)
    db.session.commit()

    return redirect(url_for("student.project_detail", project_id=project.id, _anchor="mentor-tab"))


@student_bp.route("/projects/<int:project_id>/tasks/scan-missing", methods=["POST"])
@student_required
def scan_missing_tasks(project_id: int):
    project = get_student_project_or_404(project_id)
    ai_service = get_ai_service()
    missing = ai_service.detect_missing_tasks(project, project.tasks.all())

    if missing:
        count_added = 0
        for m in missing:
            # Check if exists
            exists = Task.query.filter_by(project_id=project.id, title=m["title"]).first()
            if not exists:
                t = Task(
                    project_id=project.id,
                    title=m["title"],
                    category=m["category"],
                    priority=m["priority"],
                    difficulty=m["difficulty"],
                    status="Not Started",
                    source="AI_SUGGESTED",
                    reason=m["reason"]
                )
                db.session.add(t)
                count_added += 1
        db.session.commit()
        _sync_project_metrics_and_predict(project)
        flash(f"AI scanned your project scope and added {count_added} missing essential tasks (Testing/Validation/Documentation).", "success")
    else:
        flash("AI scan complete: No critical missing tasks detected in your project plan!", "info")

    return redirect(url_for("student.project_detail", project_id=project.id, _anchor="tasks-tab"))


@student_bp.route("/projects/<int:project_id>/what-if")
@student_required
def what_if_simulator(project_id: int):
    project = get_student_project_or_404(project_id)
    latest_progress = project.latest_progress
    latest_prediction = project.latest_prediction
    tasks = project.tasks.all()

    derived = compute_derived_features(
        total_tasks=len(tasks),
        completed_tasks=project.completed_tasks_count,
        delayed_tasks=latest_progress.delayed_tasks if latest_progress else 0,
        progress_percentage=project.calculated_progress_pct,
        testing_percentage=latest_progress.testing_percentage if latest_progress else 30.0,
        documentation_percentage=latest_progress.documentation_percentage if latest_progress else 30.0,
        bugs=latest_progress.bugs if latest_progress else 1,
        start_date=project.start_date,
        deadline=project.deadline
    )

    return render_template(
        "student/what_if.html",
        project=project,
        progress=latest_progress,
        prediction=latest_prediction,
        derived=derived
    )


@student_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@student_required
def edit_project(project_id: int):
    project = get_student_project_or_404(project_id)
    if request.method == "POST":
        project.project_name = request.form.get("project_name", project.project_name).strip()
        project.description = request.form.get("description", project.description).strip()
        project.domain = request.form.get("domain", project.domain).strip()
        project.team_size = int(request.form.get("team_size", project.team_size))
        deadline_str = request.form.get("deadline")
        if deadline_str:
            project.deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        db.session.commit()
        flash("Project settings updated.", "success")
        return redirect(url_for("student.project_detail", project_id=project.id))

    return render_template("student/project_form.html", action="Edit", project=project)


@student_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@student_required
def delete_project(project_id: int):
    project = get_student_project_or_404(project_id)
    name = project.project_name
    db.session.delete(project)
    db.session.commit()
    flash(f"Project '{name}' deleted.", "info")
    return redirect(url_for("student.dashboard"))


@student_bp.route("/alerts/<int:alert_id>/read", methods=["POST"])
@student_required
def mark_alert_read(alert_id: int):
    alert = EarlyWarningAlert.query.get_or_404(alert_id)
    if alert.project.owner_id == current_user.id:
        alert.is_read = True
        db.session.commit()
    return redirect(url_for("student.dashboard"))


def _sync_project_metrics_and_predict(project: Project) -> Prediction:
    """
    Synchronizes Task Board stats into a ProjectProgress snapshot and executes ML risk inference.
    """
    tasks = project.tasks.all()
    total = len(tasks)
    completed = project.completed_tasks_count
    blocked = project.blocked_tasks_count
    pending = total - completed
    prog_pct = project.calculated_progress_pct

    # Testing & Doc percentage based on completed tasks in those categories
    testing_tasks = [t for t in tasks if t.category == "Testing"]
    test_pct = round((sum(1 for t in testing_tasks if t.status == "Completed") / max(1, len(testing_tasks))) * 100.0, 1) if testing_tasks else 20.0

    doc_tasks = [t for t in tasks if t.category == "Documentation"]
    doc_pct = round((sum(1 for t in doc_tasks if t.status == "Completed") / max(1, len(doc_tasks))) * 100.0, 1) if doc_tasks else 25.0

    new_progress = ProjectProgress(
        project_id=project.id,
        total_tasks=total,
        completed_tasks=completed,
        pending_tasks=pending,
        delayed_tasks=0,
        blocked_tasks=blocked,
        progress_percentage=prog_pct,
        testing_percentage=test_pct,
        documentation_percentage=doc_pct,
        presentation_percentage=round(prog_pct * 0.7, 1),
        bugs=1 if blocked > 0 else 0,
        collaboration_rating=4.2,
        evaluation_score=75.0,
        notes=f"Task Board sync: {completed}/{total} completed, {blocked} blocked."
    )
    db.session.add(new_progress)
    db.session.commit()

    # Run ML Model
    ml_service = get_ml_service()
    df_row = prepare_feature_row(project, new_progress)
    pred_res = ml_service.predict_risk(df_row)

    prediction = Prediction(
        project_id=project.id,
        progress_id=new_progress.id,
        success_probability=pred_res["success_probability"],
        failure_probability=pred_res["failure_probability"],
        risk_level=pred_res["risk_level"],
        model_version=pred_res["model_version"],
        shap_values=json.dumps(pred_res.get("shap_values", [])),
        risk_factors_list=json.dumps(pred_res.get("risk_factors", []))
    )
    db.session.add(prediction)
    db.session.commit()

    # Generate Recommendations
    p_dict = {
        "progress_percentage": prog_pct,
        "testing_percentage": test_pct,
        "documentation_percentage": doc_pct,
        "presentation_percentage": round(prog_pct * 0.7, 1),
        "delayed_tasks": 0,
        "total_tasks": total,
        "completed_tasks": completed,
        "days_remaining": int(df_row["days_remaining"].iloc[0]),
        "bugs": new_progress.bugs,
        "collaboration_rating": 4.2,
        "team_size": project.team_size,
        "schedule_pressure": float(df_row["schedule_pressure"].iloc[0])
    }
    recs = generate_recommendations(p_dict, pred_res)
    for r in recs:
        db.session.add(Recommendation(
            project_id=project.id,
            prediction_id=prediction.id,
            risk_factor=r["risk_factor"],
            recommendation=r["recommendation"],
            priority=r.get("priority", "High")
        ))
    db.session.commit()

    # Check Early Warning
    check_and_create_early_warning(project, prediction)

    return prediction
