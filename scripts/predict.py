"""
CLI PREDICTION UTILITY FOR PROJEXA
==================================
Allows running quick risk predictions on sample project states directly from CLI.
"""

import sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.services.feature_engineering import prepare_raw_dict_feature_row
from app.services.ml_service import get_ml_service


def demo_cli_predict():
    print("\n--- Running Projexa CLI Risk Prediction Demo ---\n")
    ml_service = get_ml_service()

    sample_project = {
        "team_size": 3,
        "total_tasks": 20,
        "completed_tasks": 7,
        "delayed_tasks": 4,
        "progress_percentage": 35.0,
        "testing_percentage": 15.0,
        "documentation_percentage": 20.0,
        "presentation_percentage": 10.0,
        "bugs": 5,
        "technologies_count": 3,
        "technology_difficulty": "Hard",
        "project_domain": "Machine Learning & AI",
        "previous_evaluation_score": 62.0,
        "collaboration_rating": 3.2,
        "start_date": (date.today() - timedelta(days=60)).strftime("%Y-%m-%d"),
        "deadline": (date.today() + timedelta(days=12)).strftime("%Y-%m-%d"),
    }

    df_row = prepare_raw_dict_feature_row(sample_project)
    result = ml_service.predict_risk(df_row)

    print("PROJECT PARAMETERS:")
    for k, v in sample_project.items():
        print(f"  {k:28}: {v}")

    print("\n" + "=" * 50)
    print("PROJECT RISK ANALYSIS (CLI)")
    print("=" * 50)
    print(f"Success Probability: {result['success_probability']}%")
    print(f"Failure Probability: {result['failure_probability']}%")
    print(f"Risk Level:          {result['risk_level']}")
    print(f"Model Used:          {result['model_version']}")

    print("\nTOP RISK DRIVERS (Explainable AI):")
    for factor in result["risk_factors"]:
        print(f"  • {factor['feature_label']}: impact={factor['impact_score']} ({factor['direction']})")

    print("\n" + "=" * 50)
    print("IMPORTANT DISCLAIMER:")
    print("This prediction is an estimated project risk based on available project data")
    print("and historical training distributions. It is not a guarantee of academic results.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    demo_cli_predict()
