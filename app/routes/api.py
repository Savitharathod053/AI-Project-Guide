"""
REST API ENDPOINTS FOR PROJECTGUARD
==================================
JSON API for programmatic integration, mobile client access, and dynamic AJAX widgets.
"""

from datetime import datetime, date
from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from app.models import db, Project, ProjectProgress, Prediction, Recommendation, FacultyFeedback, EarlyWarningAlert
from app.services.feature_engineering import prepare_feature_row, prepare_raw_dict_feature_row, compute_derived_features
from app.services.ml_service import get_ml_service
from app.services.recommendation_engine import generate_recommendations

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
