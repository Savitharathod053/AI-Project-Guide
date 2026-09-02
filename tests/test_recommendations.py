"""Recommendation Engine and Supportive Guidance Tests."""
from app.services.recommendation_engine import generate_recommendations


def test_recommendations_generation():
    project_state = {
        "progress_percentage": 60.0,
        "testing_percentage": 10.0,  # Low testing gap
        "documentation_percentage": 15.0,
        "delayed_tasks": 3,
        "total_tasks": 20,
        "completed_tasks": 8,
        "days_remaining": 8,
        "bugs": 5,
        "collaboration_rating": 3.0,
        "team_size": 3
    }
    pred_dict = {
        "failure_probability": 65.0,
        "risk_level": "CRITICAL"
    }

    recs = generate_recommendations(project_state, pred_dict)
    assert len(recs) > 0
    
    # Check that recommendations are supportive and actionable
    rec_texts = " ".join([r["recommendation"] for r in recs])
    assert "fail" not in rec_texts.lower()  # Never discouraging
    assert "testing" in rec_texts.lower()
    assert "delayed" in rec_texts.lower() or "tasks" in rec_texts.lower()
