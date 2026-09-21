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
    ProjectCheckin, AIMentorMessage, FacultyFeedback, EarlyWarningAlert,
    ProjectResource, AIRecommendation, HardwareAnalysis
)
from app.services.ai_service import get_ai_service
from app.services.health_service import calculate_project_health_score
from app.services.feature_engineering import prepare_feature_row, compute_derived_features
from app.services.ml_service import get_ml_service
from app.services.recommendation_engine import generate_recommendations
from app.services.alert_service import check_and_create_early_warning
from app.services.resource_finder_service import get_resource_finder_service
from app.services.hardware_feasibility_service import get_hardware_feasibility_service, CONTROLLERS_DB

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

        pending_tasks = [t for t in tasks if t.status != "Completed"][:3]

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
            "days_remaining": health_info["days_remaining"],
            "pending_tasks": pending_tasks
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
    Step 1 of Project Creation: Student provides Project Title, Description,
    Domain, Deadline, Team size, and Technologies they know.
    Gemini generates the structured 6-phase task plan, AI tools, and prompts.
    """
    if request.method == "POST":
        project_name = request.form.get("project_name", "").strip()
        description = request.form.get("description", "").strip()
        domain = request.form.get("domain", "Web Development").strip()
        team_size = int(request.form.get("team_size", 1))
        technologies_known = request.form.get("technologies_known", "").strip()
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

        deadline_days = max(1, (deadline - date.today()).days)

        # 1. Automatic Project Type Classification (BuildCheck AI Detection)
        hw_service = get_hardware_feasibility_service()
        classification = hw_service.classify_project_type(
            title=project_name,
            description=description,
            domain=domain
        )
        is_hardware_project = classification["is_hardware"]
        project_category = classification["category"]

        # 2. Gemini AI Analysis (Stage 1: Deep Project Understanding)
        ai_service = get_ai_service()
        understanding = ai_service.analyze_project_understanding(
            title=project_name,
            description=description,
            domain=domain,
            technologies_known=technologies_known,
            team_size=team_size,
            deadline_days=deadline_days
        )

        suggested_tech = understanding.get("technologies", ["Python", "Flask", "SQLite"])
        tech_str = ", ".join(suggested_tech) if isinstance(suggested_tech, list) else str(suggested_tech)
        confidence = float(understanding.get("confidence_score", 85.0))
        clarification_needed = bool(understanding.get("clarification_required", False) or confidence < 80.0)

        # 3. Create Project Record
        project = Project(
            owner_id=current_user.id,
            project_name=project_name,
            description=description,
            objective=understanding.get("core_objective", "Deliver a fully working academic project."),
            project_summary=understanding.get("project_summary", ""),
            domain=understanding.get("domain", domain),
            project_type=understanding.get("project_type", classification["display_name"]),
            project_category=project_category,
            hardware_feasibility_status="PENDING_REVIEW" if is_hardware_project else "NOT_APPLICABLE",
            team_size=team_size,
            technologies_known=technologies_known,
            technology_difficulty=understanding.get("technology_difficulty", "Medium"),
            technologies=tech_str,
            technologies_count=len(suggested_tech) if isinstance(suggested_tech, list) else 3,
            ai_tools_json=json.dumps(understanding.get("ai_tools", [])),
            architecture_recommendation=understanding.get("system_architecture", ""),
            requirements_json=json.dumps(understanding),
            confidence_score=confidence,
            clarification_questions_json=json.dumps(understanding.get("clarification_questions", [])),
            plan_approved=False,
            start_date=date.today(),
            deadline=deadline
        )
        db.session.add(project)
        db.session.commit()

        # If Hardware or Hybrid, activate BuildCheck AI Hardware Feasibility Analyzer
        # Task generation is deferred until student approves the hardware architecture
        if is_hardware_project:
            hw_service.analyze_hardware_project(project)
            flash(
                f"BuildCheck AI: Detected {classification['display_name']}! Hardware components, electrical compatibility, and budget analysis are ready for review.",
                "info"
            )
            return redirect(url_for("student.hardware_feasibility", project_id=project.id))

        # Check if project requirements need student clarification (Software projects)
        if clarification_needed and understanding.get("clarification_questions"):
            flash("Gemini analyzed your project. To ensure optimal task accuracy, please answer a few brief clarifications.", "info")
            return redirect(url_for("student.clarify_project", project_id=project.id))

        # 4. Stage 2: Requirement-to-Task Generation with AI Self-Review (Software Projects)
        ai_plan = ai_service.generate_tasks_from_requirements(
            understanding=understanding,
            team_size=team_size,
            deadline_days=deadline_days
        )

        # Create Generated Phase Tasks
        tasks_created = 0
        phases = ai_plan.get("phases", [])
        if phases:
            for phase_data in phases:
                p_name = phase_data.get("name", "Phase 1 — Research & Planning")
                p_num = phase_data.get("phase_number", 1)
                for item in phase_data.get("tasks", []):
                    task = Task(
                        project_id=project.id,
                        title=item.get("title") or item.get("task_title", "Milestone Task"),
                        description=item.get("description", ""),
                        category=item.get("category", "Backend"),
                        priority=item.get("priority", "High"),
                        difficulty=item.get("difficulty", "Medium"),
                        estimated_hours=float(item.get("estimated_hours", 4.0)),
                        phase=p_name,
                        phase_number=p_num,
                        can_parallel=bool(item.get("can_parallel", False)),
                        status="Not Started",
                        is_core=item.get("priority") != "Optional",
                        is_optional=item.get("priority") == "Optional",
                        source="AI_GENERATED",
                        reason=item.get("reason", ""),
                        requirement_source=item.get("requirement_source", "")
                    )
                    db.session.add(task)
                    tasks_created += 1
        else:
            for item in ai_plan.get("core_tasks", []):
                task = Task(
                    project_id=project.id,
                    title=item.get("task_title") or item.get("title", "Milestone Task"),
                    description=item.get("description", ""),
                    category=item.get("category", "Backend"),
                    priority=item.get("priority", "High"),
                    difficulty=item.get("estimated_difficulty", "Medium"),
                    estimated_hours=float(item.get("estimated_hours", 4.0)),
                    phase=item.get("phase", "Phase 3 — Development"),
                    phase_number=item.get("phase_number", 3),
                    can_parallel=bool(item.get("can_parallel", False)),
                    status="Not Started",
                    is_core=True,
                    is_optional=False,
                    source="AI_GENERATED",
                    reason=item.get("reason", ""),
                    requirement_source=item.get("requirement_source", "")
                )
                db.session.add(task)
                tasks_created += 1

        if "ai_tools" in ai_plan and ai_plan["ai_tools"]:
            project.ai_tools_json = json.dumps(ai_plan["ai_tools"])
        if "system_architecture" in ai_plan and ai_plan["system_architecture"]:
            project.architecture_recommendation = ai_plan["system_architecture"]

        project.initial_task_count = tasks_created
        db.session.commit()

        # 4. Sync Initial Progress & ML Risk Baseline
        _sync_project_metrics_and_predict(project)

        # 5. Smart Resource Finder Analysis
        try:
            res_service = get_resource_finder_service()
            res_service.analyze_and_store_project_resources(project, project.tasks.all())
        except Exception as e:
            print(f"[-] Smart Resource Finder error during creation: {e}")

        flash("Gemini analyzed your requirements and generated your customized roadmap! Review your tasks below.", "success")
        return redirect(url_for("student.review_tasks", project_id=project.id))

    return render_template("student/project_create_ai.html")


@student_bp.route("/projects/<int:project_id>/clarify", methods=["GET", "POST"])
@student_required
def clarify_project(project_id: int):
    """
    Clarification Screen: Student answers targeted questions when initial
    project description confidence is below 80%.
    """
    project = get_student_project_or_404(project_id)
    understanding = project.get_requirements() or {}
    questions = project.get_clarification_questions()

    if request.method == "POST":
        answers = {}
        clarification_text_parts = []
        for i, q in enumerate(questions):
            ans = request.form.get(f"question_{i}", "").strip()
            if ans:
                answers[q] = ans
                clarification_text_parts.append(f"Q: {q}\nA: {ans}")

        general_notes = request.form.get("general_notes", "").strip()
        if general_notes:
            clarification_text_parts.append(f"Additional notes: {general_notes}")

        project.clarification_answers_json = json.dumps(answers)

        if clarification_text_parts:
            clarification_text = "\n\nStudent Clarifications:\n" + "\n".join(clarification_text_parts)
            project.description = (project.description or "") + clarification_text

        # Re-run Stage 1 with enriched description
        ai_service = get_ai_service()
        enriched_understanding = ai_service.analyze_project_understanding(
            title=project.project_name,
            description=project.description,
            domain=project.domain,
            technologies_known=project.technologies_known,
            team_size=project.team_size,
            deadline_days=max(1, (project.deadline - date.today()).days if project.deadline else 90)
        )
        if enriched_understanding.get("confidence_score", 0) < 85:
            enriched_understanding["confidence_score"] = 92.0
            enriched_understanding["clarification_required"] = False

        project.requirements_json = json.dumps(enriched_understanding)
        project.confidence_score = enriched_understanding.get("confidence_score", 92.0)
        project.objective = enriched_understanding.get("core_objective", project.objective)

        # Stage 2: Generate tasks from enriched requirements
        ai_plan = ai_service.generate_tasks_from_requirements(
            understanding=enriched_understanding,
            team_size=project.team_size,
            deadline_days=max(1, (project.deadline - date.today()).days if project.deadline else 90)
        )

        Task.query.filter_by(project_id=project.id).delete()
        db.session.commit()

        tasks_created = 0
        phases = ai_plan.get("phases", [])
        if phases:
            for phase_data in phases:
                p_name = phase_data.get("name", "Phase 1 — Research & Planning")
                p_num = phase_data.get("phase_number", 1)
                for item in phase_data.get("tasks", []):
                    task = Task(
                        project_id=project.id,
                        title=item.get("title") or item.get("task_title", "Milestone Task"),
                        description=item.get("description", ""),
                        category=item.get("category", "Backend"),
                        priority=item.get("priority", "High"),
                        difficulty=item.get("difficulty", "Medium"),
                        estimated_hours=float(item.get("estimated_hours", 4.0)),
                        phase=p_name,
                        phase_number=p_num,
                        can_parallel=bool(item.get("can_parallel", False)),
                        status="Not Started",
                        is_core=item.get("priority") != "Optional",
                        is_optional=item.get("priority") == "Optional",
                        source="AI_GENERATED",
                        reason=item.get("reason", ""),
                        requirement_source=item.get("requirement_source", "")
                    )
                    db.session.add(task)
                    tasks_created += 1
        else:
            for item in ai_plan.get("core_tasks", []):
                task = Task(
                    project_id=project.id,
                    title=item.get("task_title") or item.get("title", "Milestone Task"),
                    description=item.get("description", ""),
                    category=item.get("category", "Backend"),
                    priority=item.get("priority", "High"),
                    difficulty=item.get("estimated_difficulty", "Medium"),
                    estimated_hours=float(item.get("estimated_hours", 4.0)),
                    phase=item.get("phase", "Phase 3 — Development"),
                    phase_number=item.get("phase_number", 3),
                    can_parallel=bool(item.get("can_parallel", False)),
                    status="Not Started",
                    is_core=True,
                    is_optional=False,
                    source="AI_GENERATED",
                    reason=item.get("reason", ""),
                    requirement_source=item.get("requirement_source", "")
                )
                db.session.add(task)
                tasks_created += 1

        if "ai_tools" in ai_plan and ai_plan["ai_tools"]:
            project.ai_tools_json = json.dumps(ai_plan["ai_tools"])
        if "system_architecture" in ai_plan and ai_plan["system_architecture"]:
            project.architecture_recommendation = ai_plan["system_architecture"]

        project.initial_task_count = tasks_created
        db.session.commit()

        _sync_project_metrics_and_predict(project)

        try:
            res_service = get_resource_finder_service()
            res_service.analyze_and_store_project_resources(project, project.tasks.all())
        except Exception as e:
            print(f"[-] Smart Resource Finder error after clarification: {e}")

        flash("Clarifications applied! Your customized project roadmap is ready.", "success")
        return redirect(url_for("student.review_tasks", project_id=project.id))

    return render_template(
        "student/project_clarify.html",
        project=project,
        understanding=understanding,
        questions=questions
    )


@student_bp.route("/projects/<int:project_id>/review-tasks")
@student_required
def review_tasks(project_id: int):
    """
    Step 2: Student reviews Gemini-generated tasks organized by 6 phases.
    Allows adding, editing, deleting, or regenerating tasks.
    """
    project = get_student_project_or_404(project_id)
    tasks = project.tasks.all()
    
    # Group tasks by phase
    phases_dict = {}
    for t in tasks:
        p_name = t.phase or f"Phase {t.phase_number} — Development"
        if p_name not in phases_dict:
            phases_dict[p_name] = {
                "name": p_name,
                "phase_number": t.phase_number,
                "tasks": []
            }
        phases_dict[p_name]["tasks"].append(t)
        
    phases_list = sorted(phases_dict.values(), key=lambda x: x["phase_number"])
    total_hours = sum(t.estimated_hours for t in tasks)

    return render_template(
        "student/task_review.html",
        project=project,
        understanding=project.get_requirements(),
        phases_list=phases_list,
        core_tasks=[t for t in tasks if not t.is_optional],
        optional_tasks=[t for t in tasks if t.is_optional],
        total_tasks=len(tasks),
        total_hours=total_hours
    )


@student_bp.route("/projects/<int:project_id>/buildcheck", methods=["GET", "POST"])
@student_required
def hardware_feasibility(project_id: int):
    """
    BuildCheck AI: Hardware Feasibility & Budget Analyzer Dashboard.
    Allows student to view system architecture, BOM, electrical checks,
    budget breakdown, online purchasing options, and adjust parameters.
    """
    project = get_student_project_or_404(project_id)
    hw_service = get_hardware_feasibility_service()

    if request.method == "POST":
        try:
            student_budget = float(request.form.get("student_budget", 2000.0) or 2000.0)
        except (ValueError, TypeError):
            student_budget = 2000.0

        preferred_controller = request.form.get("preferred_controller", "ESP32").strip()
        preferred_marketplace = request.form.get("preferred_marketplace", "Robu.in").strip()
        
        # Available components checklist
        available_raw = request.form.getlist("available_components")
        if not available_raw:
            available_text = request.form.get("available_components_text", "").strip()
            if available_text:
                available_raw = [c.strip() for c in available_text.split(",") if c.strip()]

        analysis = hw_service.analyze_hardware_project(
            project=project,
            student_budget=student_budget,
            available_components=available_raw,
            preferred_controller=preferred_controller,
            preferred_marketplace=preferred_marketplace
        )
        flash("Hardware feasibility parameters updated and recalculated!", "success")
        return redirect(url_for("student.hardware_feasibility", project_id=project.id))

    analysis = HardwareAnalysis.query.filter_by(project_id=project.id).first()
    if not analysis:
        analysis = hw_service.analyze_hardware_project(project)

    return render_template(
        "student/hardware_feasibility.html",
        project=project,
        analysis=analysis,
        bom=analysis.get_bom(),
        inputs=analysis.get_inputs(),
        processing=analysis.get_processing(),
        outputs=analysis.get_outputs(),
        communication=analysis.get_communication(),
        power=analysis.get_power(),
        compatibility_issues=analysis.get_compatibility_issues(),
        gpio_analysis=analysis.get_gpio_analysis(),
        wiring_table=analysis.get_wiring_table(),
        software_reqs=analysis.get_software_reqs(),
        testing_verification=analysis.get_testing_verification(),
        feasibility_checks=analysis.get_feasibility_checks(),
        troubleshooting=analysis.get_troubleshooting(),
        budget_tiers=analysis.get_budget_tiers(),
        processing_logic=analysis.processing_logic_text or "",
        expected_output=analysis.expected_output_text or "",
        budget_data=analysis.to_dict()["budget"],
        modifications=analysis.get_modifications(),
        products=analysis.get_products(),
        controllers_db=CONTROLLERS_DB,
        primary_components=analysis.get_primary_components(),
        supporting_components=analysis.get_supporting_components(),
        power_architecture=analysis.get_power_architecture(),
        feasibility_verification=analysis.get_feasibility_verification(),
        project_understanding=analysis.get_project_understanding()
    )


@student_bp.route("/projects/<int:project_id>/buildcheck/approve", methods=["POST"])
@student_required
def approve_hardware_architecture(project_id: int):
    """
    Student confirms and approves the hardware architecture & BOM.
    Generates specialized 6-phase hardware development tasks and redirects to Task Review.
    """
    project = get_student_project_or_404(project_id)
    hw_service = get_hardware_feasibility_service()

    # Generate specialized 6-phase hardware tasks based on approved BOM
    created_tasks = hw_service.generate_hardware_tasks(project)

    # Sync metrics & predictions
    _sync_project_metrics_and_predict(project)

    # Smart resources finder
    try:
        res_service = get_resource_finder_service()
        res_service.analyze_and_store_project_resources(project, project.tasks.all())
    except Exception as e:
        print(f"[-] Smart Resource Finder error during hardware approval: {e}")

    flash(
        "Hardware architecture approved! Your specialized 6-phase development roadmap with circuit, firmware, and testing tasks has been generated.",
        "success"
    )
    return redirect(url_for("student.review_tasks", project_id=project.id))


@student_bp.route("/projects/<int:project_id>/approve-roadmap", methods=["POST"])
@student_required
def approve_roadmap(project_id: int):
    """Student explicitly approves the customized project plan and opens the workspace."""
    project = get_student_project_or_404(project_id)
    project.plan_approved = True
    db.session.commit()
    _sync_project_metrics_and_predict(project)
    flash("Project development roadmap approved! Your tracking workspace is ready.", "success")
    return redirect(url_for("student.project_detail", project_id=project.id))


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

    # Derived ML features
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

    # AI Guidance & Pacing
    ai_service = get_ai_service()
    guidance = ai_service.analyze_progress_and_guidance(project, tasks)
    ai_tools = project.get_ai_tools()
    pacing = project.get_timeline_pacing()

    # Group tasks by phase for structured viewing
    phases_dict = {}
    for t in tasks:
        p_name = t.phase or f"Phase {t.phase_number} — Development"
        if p_name not in phases_dict:
            phases_dict[p_name] = {
                "name": p_name,
                "phase_number": t.phase_number,
                "tasks": []
            }
        phases_dict[p_name]["tasks"].append(t)
    phases_list = sorted(phases_dict.values(), key=lambda x: x["phase_number"])

    checkins = project.checkins.limit(5).all()
    chat_messages = project.chat_messages.limit(20).all()
    recommendations = latest_prediction.recommendations.all() if latest_prediction else []
    feedback_list = project.feedback_records.all()
    alerts = project.alerts.all()

    # Smart Resources & AI Recommendations
    resources = project.resources.all()
    if not resources:
        try:
            res_service = get_resource_finder_service()
            res_service.analyze_and_store_project_resources(project, tasks)
            resources = project.resources.all()
        except Exception as e:
            print(f"[-] Auto-init project resources error: {e}")
            resources = []

    ai_recs = project.ai_recommendations.all()
    api_resources = [r for r in resources if r.resource_type == "api"]
    dataset_resources = [r for r in resources if r.resource_type == "dataset"]
    tool_resources = [r for r in resources if r.resource_type in ("ai_tool", "tool", "documentation")]

    return render_template(
        "student/project_detail.html",
        project=project,
        tasks=tasks,
        phases_list=phases_list,
        progress=latest_progress,
        prediction=latest_prediction,
        health_info=health_info,
        guidance=guidance,
        pacing=pacing,
        ai_tools=ai_tools,
        derived=derived,
        history_json=json.dumps(history_data),
        checkins=checkins,
        chat_messages=chat_messages,
        recommendations=recommendations,
        feedback_list=feedback_list,
        alerts=alerts,
        resources=resources,
        api_resources=api_resources,
        dataset_resources=dataset_resources,
        tool_resources=tool_resources,
        ai_recommendations=ai_recs
    )


@student_bp.route("/projects/<int:project_id>/resources/refresh", methods=["POST"])
@student_required
def refresh_project_resources(project_id: int):
    """Refreshes and regenerates smart resources and AI tool prompts for the project."""
    project = get_student_project_or_404(project_id)
    try:
        service = get_resource_finder_service()
        service.analyze_and_store_project_resources(project, project.tasks.all())
        flash("Smart resources and contextual AI prompts refreshed successfully from official developer sources!", "success")
    except Exception as e:
        flash(f"Could not refresh resources: {e}", "warning")
    return redirect(url_for("student.project_detail", project_id=project.id) + "#resources")


@student_bp.route("/projects/<int:project_id>/tasks/add", methods=["POST"])
@student_required
def add_task(project_id: int):
    project = get_student_project_or_404(project_id)
    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title cannot be empty.", "warning")
        return redirect(request.referrer or url_for("student.project_detail", project_id=project.id, _anchor="tasks-tab"))

    # Evaluate task with AI for duplicate detection, categorization and phase assignment
    ai_service = get_ai_service()
    eval_res = ai_service.evaluate_additional_task(project, title, project.tasks.all())

    phase = request.form.get("phase", eval_res.get("phase", "Phase 3 — Development"))
    phase_number = eval_res.get("phase_number", 3)
    if "Phase 1" in phase: phase_number = 1
    elif "Phase 2" in phase: phase_number = 2
    elif "Phase 3" in phase: phase_number = 3
    elif "Phase 4" in phase: phase_number = 4
    elif "Phase 5" in phase: phase_number = 5
    elif "Phase 6" in phase: phase_number = 6

    try:
        est_hours = float(request.form.get("estimated_hours", eval_res.get("estimated_hours", 4.0)))
    except ValueError:
        est_hours = 4.0

    task = Task(
        project_id=project.id,
        title=eval_res["title"],
        description=request.form.get("description", "").strip() or eval_res["message"],
        category=request.form.get("category", eval_res["category"]),
        priority=request.form.get("priority", eval_res["priority"]),
        difficulty=request.form.get("difficulty", "Medium"),
        estimated_hours=est_hours,
        phase=phase,
        phase_number=phase_number,
        status="Not Started",
        is_core=bool(request.form.get("is_core", True)),
        is_optional=not bool(request.form.get("is_core", True)),
        source="STUDENT_ADDED"
    )
    db.session.add(task)
    db.session.commit()

    _sync_project_metrics_and_predict(project)

    if eval_res["is_duplicate"]:
        flash(f"⚠️ Notice: '{title}' appears similar to existing task '{eval_res['duplicate_of']}', but was added to {phase}.", "info")
    else:
        flash(f"Task '{title}' added to {phase}.", "success")

    return redirect(request.referrer or url_for("student.project_detail", project_id=project.id, _anchor="tasks-tab"))


@student_bp.route("/projects/<int:project_id>/tasks/<int:task_id>/edit", methods=["POST"])
@student_required
def edit_task(project_id: int, task_id: int):
    """Allows student to edit task details (title, description, priority, category, phase, estimated_hours)."""
    project = get_student_project_or_404(project_id)
    task = Task.query.filter_by(id=task_id, project_id=project.id).first_or_404()

    task.title = request.form.get("title", task.title).strip()
    task.description = request.form.get("description", task.description).strip()
    task.category = request.form.get("category", task.category).strip()
    task.priority = request.form.get("priority", task.priority).strip()
    task.difficulty = request.form.get("difficulty", task.difficulty).strip()
    
    if "phase" in request.form:
        task.phase = request.form.get("phase", task.phase).strip()
        if "Phase 1" in task.phase: task.phase_number = 1
        elif "Phase 2" in task.phase: task.phase_number = 2
        elif "Phase 3" in task.phase: task.phase_number = 3
        elif "Phase 4" in task.phase: task.phase_number = 4
        elif "Phase 5" in task.phase: task.phase_number = 5
        elif "Phase 6" in task.phase: task.phase_number = 6

    try:
        task.estimated_hours = float(request.form.get("estimated_hours", task.estimated_hours))
    except ValueError:
        pass

    if "status" in request.form:
        task.status = request.form.get("status", task.status)

    db.session.commit()
    _sync_project_metrics_and_predict(project)

    flash(f"Task '{task.title}' updated successfully.", "success")
    return redirect(request.referrer or url_for("student.review_tasks", project_id=project.id))


@student_bp.route("/projects/<int:project_id>/tasks/regenerate", methods=["POST"])
@student_required
def regenerate_tasks(project_id: int):
    """Regenerates the complete project roadmap using Gemini."""
    project = get_student_project_or_404(project_id)
    instructions = request.form.get("instructions", "").strip()

    ai_service = get_ai_service()
    plan = ai_service.regenerate_project_tasks(project, instructions)

    # Remove existing tasks
    Task.query.filter_by(project_id=project.id).delete()
    db.session.commit()

    # Re-insert regenerated tasks
    phases = plan.get("phases", [])
    count = 0
    if phases:
        for p in phases:
            p_name = p.get("name", "Phase 1 — Research & Planning")
            p_num = p.get("phase_number", 1)
            for item in p.get("tasks", []):
                t = Task(
                    project_id=project.id,
                    title=item.get("title") or item.get("task_title", "Task"),
                    description=item.get("description", ""),
                    category=item.get("category", "Backend"),
                    priority=item.get("priority", "High"),
                    difficulty=item.get("difficulty", "Medium"),
                    estimated_hours=float(item.get("estimated_hours", 4.0)),
                    phase=p_name,
                    phase_number=p_num,
                    can_parallel=bool(item.get("can_parallel", False)),
                    status="Not Started",
                    is_core=item.get("priority") != "Optional",
                    is_optional=item.get("priority") == "Optional",
                    source="AI_GENERATED",
                    reason=item.get("reason", ""),
                    requirement_source=item.get("requirement_source", "")
                )
                db.session.add(t)
                count += 1
    else:
        for item in plan.get("core_tasks", []):
            t = Task(
                project_id=project.id,
                title=item.get("task_title") or item.get("title", "Task"),
                description=item.get("description", ""),
                category=item.get("category", "Backend"),
                priority=item.get("priority", "High"),
                difficulty=item.get("estimated_difficulty", "Medium"),
                estimated_hours=float(item.get("estimated_hours", 4.0)),
                phase=item.get("phase", "Phase 3 — Development"),
                phase_number=item.get("phase_number", 3),
                can_parallel=bool(item.get("can_parallel", False)),
                status="Not Started",
                is_core=True,
                is_optional=False,
                source="AI_GENERATED",
                reason=item.get("reason", ""),
                requirement_source=item.get("requirement_source", "")
            )
            db.session.add(t)
            count += 1

    if "ai_tools" in plan:
        project.ai_tools_json = json.dumps(plan["ai_tools"])
    if "system_architecture" in plan:
        project.architecture_recommendation = plan["system_architecture"]

    project.initial_task_count = count
    db.session.commit()

    _sync_project_metrics_and_predict(project)
    flash(f"Gemini regenerated your project plan ({count} tasks across 6 phases)!", "success")
    return redirect(request.referrer or url_for("student.review_tasks", project_id=project.id))


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

    return redirect(request.referrer or url_for("student.project_detail", project_id=project.id, _anchor="tasks-tab"))


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
    return redirect(request.referrer or url_for("student.project_detail", project_id=project.id, _anchor="tasks-tab"))


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
