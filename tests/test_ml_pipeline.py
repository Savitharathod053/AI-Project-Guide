"""ML Preprocessing, Feature Engineering, and Inference Tests."""
from datetime import date, timedelta
import pandas as pd
import pytest
from app.services.feature_engineering import compute_derived_features, prepare_raw_dict_feature_row
from app.services.ml_service import get_ml_service


def test_feature_engineering_safeguards():
    # Test zero-division resilience
    derived = compute_derived_features(
        total_tasks=0,
        completed_tasks=0,
        delayed_tasks=0,
        progress_percentage=0.0,
        testing_percentage=0.0,
        documentation_percentage=0.0,
        bugs=0,
        start_date=date.today(),
        deadline=date.today()  # 0 days remaining
    )

    assert derived["completion_ratio"] == 0.0
    assert derived["delay_ratio"] == 0.0
    assert derived["schedule_pressure"] == 0.0
    assert derived["days_remaining"] == 0


def test_raw_dict_feature_row_preparation():
    data = {
        "team_size": 3,
        "total_tasks": 20,
        "completed_tasks": 10,
        "delayed_tasks": 2,
        "progress_percentage": 50.0,
        "testing_percentage": 40.0,
        "documentation_percentage": 30.0,
        "bugs": 2,
        "technologies_count": 4,
        "technology_difficulty": "Medium",
        "project_domain": "Web Development",
        "start_date": "2026-01-01",
        "deadline": "2026-06-01"
    }
    df = prepare_raw_dict_feature_row(data)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert "completion_ratio" in df.columns
    assert "schedule_pressure" in df.columns


def test_ml_service_inference():
    ml_service = get_ml_service()
    assert ml_service.is_ready is True

    sample = {
        "team_size": 2,
        "total_tasks": 15,
        "completed_tasks": 12,
        "delayed_tasks": 0,
        "progress_percentage": 80.0,
        "testing_percentage": 75.0,
        "documentation_percentage": 70.0,
        "presentation_percentage": 60.0,
        "bugs": 1,
        "technologies_count": 2,
        "technology_difficulty": "Easy",
        "project_domain": "Mobile Applications",
        "days_remaining": 20
    }
    df_row = prepare_raw_dict_feature_row(sample)
    pred = ml_service.predict_risk(df_row)

    assert "success_probability" in pred
    assert "failure_probability" in pred
    assert "risk_level" in pred
    assert 0.0 <= pred["success_probability"] <= 100.0
    assert 0.0 <= pred["failure_probability"] <= 100.0
    assert pred["risk_level"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
