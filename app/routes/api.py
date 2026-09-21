"""
REST API ENDPOINTS FOR PROJECTGUARD
==================================
JSON API for programmatic integration, mobile client access, and dynamic AJAX widgets.
"""

from datetime import datetime, date
from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from app.models import (
    db, Project, Task, ProjectProgress, Prediction, Recommendation,
    FacultyFeedback, EarlyWarningAlert, ProjectResource, AIRecommendation,
    HardwareAnalysis
)
from app.services.feature_engineering import prepare_feature_row, prepare_raw_dict_feature_row, compute_derived_features
from app.services.ml_service import get_ml_service
from app.services.recommendation_engine import generate_recommendations
from app.services.resource_finder_service import get_resource_finder_service
from app.services.hardware_feasibility_service import get_hardware_feasibility_service

api_bp = Blueprint("api", __name__)


@api_bp.route("/projects", methods=["GET"])
@login_required
def api_get_projects():
    if current_user.is_student:
        projects = Project.query.filter_by(owner_id=current_user.id).all()
    else:
        projects = Project.query.all()

    data = []
    for p in projects:
        pred = p.latest_prediction
        prog = p.latest_progress
        data.append({
            "id": p.id,
            "project_name": p.project_name,
            "domain": p.domain,
            "team_size": p.team_size,
            "start_date": p.start_date.isoformat(),
            "deadline": p.deadline.isoformat(),
            "progress_percentage": prog.progress_percentage if prog else 0.0,
            "risk_level": pred.risk_level if pred else "NOT ASSESSED",
            "failure_probability": pred.failure_probability if pred else None,
            "success_probability": pred.success_probability if pred else None,
            "owner": p.owner.name if p.owner else "Unknown"
        })
    return jsonify({"status": "success", "count": len(data), "data": data})


@api_bp.route("/projects/<int:project_id>", methods=["GET"])
@login_required
def api_get_project(project_id: int):
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    prog = project.latest_progress
    pred = project.latest_prediction

    return jsonify({
        "status": "success",
        "data": {
            "id": project.id,
            "project_name": project.project_name,
            "domain": project.domain,
            "team_size": project.team_size,
            "technologies": project.technologies,
            "technology_difficulty": project.technology_difficulty,
            "start_date": project.start_date.isoformat(),
            "deadline": project.deadline.isoformat(),
            "progress": {
                "total_tasks": prog.total_tasks if prog else 0,
                "completed_tasks": prog.completed_tasks if prog else 0,
                "delayed_tasks": prog.delayed_tasks if prog else 0,
                "progress_percentage": prog.progress_percentage if prog else 0,
                "testing_percentage": prog.testing_percentage if prog else 0,
                "documentation_percentage": prog.documentation_percentage if prog else 0,
                "bugs": prog.bugs if prog else 0
            } if prog else None,
            "prediction": {
                "success_probability": pred.success_probability if pred else None,
                "failure_probability": pred.failure_probability if pred else None,
                "risk_level": pred.risk_level if pred else None,
                "model_version": pred.model_version if pred else None,
                "risk_factors": pred.get_risk_factors() if pred else []
            } if pred else None
        }
    })


@api_bp.route("/projects/<int:project_id>/history", methods=["GET"])
@login_required
def api_get_history(project_id: int):
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    history = Prediction.query.filter_by(project_id=project.id).order_by(Prediction.created_at.asc()).all()
    points = [
        {
            "id": h.id,
            "timestamp": h.created_at.isoformat(),
            "date_label": h.created_at.strftime("%b %d, %Y"),
            "failure_probability": h.failure_probability,
            "success_probability": h.success_probability,
            "risk_level": h.risk_level
        }
        for h in history
    ]
    return jsonify({"status": "success", "project_id": project.id, "history": points})


@api_bp.route("/projects/<int:project_id>/what-if", methods=["POST"])
@login_required
def api_what_if_simulation(project_id: int):
    """
    Runs hypothetical scenario prediction using the real ML model.
    Does NOT mutate database state.
    """
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    data = request.get_json() or {}

    # Current baseline prediction
    baseline_pred = project.latest_prediction
    current_failure_prob = float(baseline_pred.failure_probability) if baseline_pred else 50.0

    # Build simulation payload
    sim_data = {
        "team_size": int(data.get("team_size", project.team_size)),
        "technology_difficulty": data.get("technology_difficulty", project.technology_difficulty),
        "project_domain": project.domain,
        "total_tasks": int(data.get("total_tasks", 10)),
        "completed_tasks": int(data.get("completed_tasks", 0)),
        "delayed_tasks": int(data.get("delayed_tasks", 0)),
        "progress_percentage": float(data.get("progress_percentage", 0.0)),
        "testing_percentage": float(data.get("testing_percentage", 0.0)),
        "documentation_percentage": float(data.get("documentation_percentage", 0.0)),
        "presentation_percentage": float(data.get("presentation_percentage", 0.0)),
        "bugs": int(data.get("bugs", 0)),
        "technologies_count": project.technologies_count,
        "collaboration_rating": float(data.get("collaboration_rating", 4.0)),
        "previous_evaluation_score": float(data.get("previous_evaluation_score", 70.0)),
        "start_date": project.start_date.strftime("%Y-%m-%d"),
        "deadline": project.deadline.strftime("%Y-%m-%d"),
        "days_remaining": int(data.get("days_remaining", 30))
    }

    # Run ML Model
    ml_service = get_ml_service()
    df_row = prepare_raw_dict_feature_row(sim_data)
    sim_result = ml_service.predict_risk(df_row)

    new_failure_prob = float(sim_result["failure_probability"])
    new_success_prob = float(sim_result["success_probability"])
    
    # Calculate improvement delta (positive means risk decreased)
    risk_improvement = round(current_failure_prob - new_failure_prob, 1)

    # Derived recommendations for the simulated state
    recs = generate_recommendations(sim_data, sim_result)

    return jsonify({
        "status": "success",
        "current_failure_probability": current_failure_prob,
        "simulated_failure_probability": new_failure_prob,
        "simulated_success_probability": new_success_prob,
        "simulated_risk_level": sim_result["risk_level"],
        "simulated_risk_badge": sim_result["risk_badge"],
        "risk_improvement": risk_improvement,
        "is_improved": risk_improvement > 0,
        "risk_factors": sim_result["risk_factors"],
        "recommendations": recs,
        "model_version": sim_result["model_version"]
    })


@api_bp.route("/model/info", methods=["GET"])
def api_model_info():
    ml_service = get_ml_service()
    return jsonify({
        "status": "success",
        "is_ready": ml_service.is_ready,
        "metadata": ml_service.metadata or {}
    })


# ==============================================================================
# SMART RESOURCE FINDER & AI TOOL ADVISOR API ENDPOINTS
# ==============================================================================

@api_bp.route("/projects/<int:project_id>/resources/analyze", methods=["POST"])
@login_required
def api_analyze_project_resources(project_id: int):
    """
    Triggers Gemini project analysis to determine required APIs, Datasets, and AI Tools,
    resolves official verified links, and stores them in the database.
    """
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    service = get_resource_finder_service()
    tasks = project.tasks.all()
    result = service.analyze_and_store_project_resources(project, tasks)

    resources = [r.to_dict() for r in project.resources.all()]
    ai_recs = [t.to_dict() for t in project.ai_recommendations.all()]

    return jsonify({
        "status": "success",
        "message": f"Successfully analyzed project and identified {len(resources)} verified resources.",
        "project_id": project.id,
        "resources_count": len(resources),
        "resources": resources,
        "ai_recommendations": ai_recs
    })


@api_bp.route("/projects/<int:project_id>/resources", methods=["GET"])
@login_required
def api_get_project_resources(project_id: int):
    """
    Returns all verified resources for a project, optionally filtered by type (api, dataset, ai_tool)
    or task_id.
    """
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    res_type = request.args.get("type")
    task_id = request.args.get("task_id", type=int)

    query = ProjectResource.query.filter_by(project_id=project.id)
    if res_type:
        query = query.filter_by(resource_type=res_type.lower())
    if task_id is not None:
        query = query.filter_by(task_id=task_id)

    resources = query.order_by(ProjectResource.created_at.asc()).all()
    ai_recs = project.ai_recommendations.order_by(AIRecommendation.created_at.asc()).all()

    return jsonify({
        "status": "success",
        "project_id": project.id,
        "count": len(resources),
        "resources": [r.to_dict() for r in resources],
        "ai_recommendations": [a.to_dict() for a in ai_recs]
    })


@api_bp.route("/projects/<int:project_id>/resources/refresh", methods=["POST"])
@login_required
def api_refresh_project_resources(project_id: int):
    """
    Refreshes and regenerates resource recommendations based on latest project status and tasks.
    """
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    service = get_resource_finder_service()
    tasks = project.tasks.all()
    result = service.analyze_and_store_project_resources(project, tasks)

    resources = [r.to_dict() for r in project.resources.all()]
    return jsonify({
        "status": "success",
        "message": "Project resources refreshed successfully.",
        "project_id": project.id,
        "resources": resources
    })


@api_bp.route("/projects/<int:project_id>/tasks/<int:task_id>/resources", methods=["GET"])
@login_required
def api_get_task_resources(project_id: int, task_id: int):
    """
    Returns verified APIs, Datasets, or AI Tools directly linked to an individual task.
    """
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    task = Task.query.filter_by(id=task_id, project_id=project.id).first_or_404()
    resources = task.resources.all()
    ai_recs = task.ai_recommendations.all()

    return jsonify({
        "status": "success",
        "project_id": project.id,
        "task_id": task.id,
        "task_title": task.title,
        "resources": [r.to_dict() for r in resources],
        "ai_recommendations": [a.to_dict() for a in ai_recs]
    })


@api_bp.route("/projects/<int:project_id>/ai-tools/recommend", methods=["POST", "GET"])
@login_required
def api_recommend_ai_tools(project_id: int):
    """
    Generates contextual AI tool recommendations for software-related project stages.
    """
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    service = get_resource_finder_service()
    tasks = project.tasks.all()
    recommendations = service.generate_ai_tool_recommendations(project, tasks)

    return jsonify({
        "status": "success",
        "project_id": project.id,
        "tools": recommendations
    })


@api_bp.route("/projects/<int:project_id>/ai-tools/generate-prompt", methods=["POST"])
@login_required
def api_generate_ai_prompt(project_id: int):
    """
    Generates an engineered prompt specifically tailored to the student's project and task.
    """
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    data = request.get_json() or {}
    tool_purpose = data.get("purpose", "Coding")
    task_title = data.get("task_title", "Project Implementation")
    custom_context = data.get("context", "")

    tech = project.technologies or "Python, Flask, PostgreSQL"
    prompt_text = (
        f"I am building '{project.project_name}' in domain '{project.domain}' using {tech}. "
        f"Goal / Task: {task_title}. "
        f"{('Additional Context: ' + custom_context) if custom_context else ''} "
        f"Please analyze the technical requirements first, then provide clean, modular, production-ready "
        f"implementation steps with docstrings and error handling. Do not alter unrelated files."
    )

    return jsonify({
        "status": "success",
        "project_id": project.id,
        "purpose": tool_purpose,
        "task_title": task_title,
        "prompt": prompt_text
    })


@api_bp.route("/projects/<int:project_id>/resources/<int:resource_id>/verify", methods=["POST"])
@login_required
def api_verify_resource(project_id: int, resource_id: int):
    """
    Validates and updates the verification status of a resource.
    """
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    resource = ProjectResource.query.filter_by(id=resource_id, project_id=project.id).first_or_404()
    
    # Check if official_url is valid
    if resource.official_url and (resource.official_url.startswith("http://") or resource.official_url.startswith("https://")):
        resource.verification_status = "Verified"
    else:
        resource.verification_status = "Community Source"

    db.session.commit()

    return jsonify({
        "status": "success",
        "resource": resource.to_dict()
    })


# ==============================================================================
# BUILDCHECK AI — HARDWARE FEASIBILITY REST API ENDPOINTS
# ==============================================================================

@api_bp.route("/projects/<int:project_id>/buildcheck/data", methods=["GET"])
@login_required
def api_get_hardware_feasibility_data(project_id: int):
    """Returns the full JSON data structure of the project's hardware feasibility analysis."""
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    hw_service = get_hardware_feasibility_service()
    analysis = HardwareAnalysis.query.filter_by(project_id=project.id).first()
    if not analysis:
        analysis = hw_service.analyze_hardware_project(project)

    return jsonify({
        "status": "success",
        "project_id": project.id,
        "project_name": project.project_name,
        "data": analysis.to_dict()
    })


@api_bp.route("/projects/<int:project_id>/buildcheck/recalculate", methods=["POST"])
@login_required
def api_recalculate_hardware_feasibility(project_id: int):
    """AJAX endpoint to recalculate hardware feasibility when student adjusts budget or components."""
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    payload = request.get_json() or {}
    student_budget = float(payload.get("student_budget", 2000.0))
    preferred_controller = payload.get("preferred_controller", "ESP32")
    preferred_marketplace = payload.get("preferred_marketplace", "Robu.in")
    available_components = payload.get("available_components", [])

    hw_service = get_hardware_feasibility_service()
    analysis = hw_service.analyze_hardware_project(
        project=project,
        student_budget=student_budget,
        available_components=available_components,
        preferred_controller=preferred_controller,
        preferred_marketplace=preferred_marketplace
    )

    return jsonify({
        "status": "success",
        "message": "Hardware feasibility recalculated successfully.",
        "data": analysis.to_dict()
    })


@api_bp.route("/projects/<int:project_id>/buildcheck/options/<path:component_name>", methods=["GET"])
@login_required
def api_get_component_purchase_options(project_id: int, component_name: str):
    """Returns verified 3-tier purchasing options with real links for any component."""
    project = Project.query.get_or_404(project_id)
    if current_user.is_student and project.owner_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    hw_service = get_hardware_feasibility_service()
    options_data = hw_service.get_online_purchase_options(component_name)

    return jsonify({
        "status": "success",
        "component_name": component_name,
        "data": options_data
    })

