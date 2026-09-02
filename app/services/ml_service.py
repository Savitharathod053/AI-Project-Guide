"""
MACHINE LEARNING INFERENCE AND EXPLAINABLE AI SERVICE
=====================================================
Loads trained models and ColumnTransformer pipelines.
Provides fast inference, SHAP/attribution explainability, and risk categorizations.
"""

import json
import os
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from app.ml.config import get_risk_level_info

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "trained_model.pkl"
PIPELINE_PATH = MODELS_DIR / "pipeline.pkl"
FEATURE_CONFIG_PATH = MODELS_DIR / "feature_config.json"
METADATA_PATH = MODELS_DIR / "model_metadata.json"

FEATURE_LABELS = {
    "team_size": "Team Size",
    "total_tasks": "Total Task Count",
    "completed_tasks": "Completed Tasks",
    "pending_tasks": "Pending Tasks",
    "delayed_tasks": "Delayed Tasks",
    "progress_percentage": "Overall Progress %",
    "testing_percentage": "Testing Percentage %",
    "documentation_percentage": "Documentation %",
    "presentation_percentage": "Presentation Prep %",
    "bugs": "Reported Bugs",
    "technologies_count": "Tech Stack Count",
    "previous_evaluation_score": "Previous Evaluation Score",
    "days_remaining": "Days Until Deadline",
    "collaboration_rating": "Team Collaboration Rating",
    "completion_ratio": "Task Completion Ratio",
    "delay_ratio": "Task Delay Ratio",
    "remaining_work": "Remaining Work Tasks",
    "schedule_pressure": "Schedule Pressure",
    "test_coverage_gap": "Test Coverage Gap",
    "doc_coverage_gap": "Documentation Gap",
    "bug_density": "Bug Density per Completed Task",
    "technology_difficulty": "Tech Stack Difficulty",
    "project_domain": "Project Domain"
}


class MLService:
    _instance = None

    def __init__(self):
        self.model = None
        self.pipeline = None
        self.feature_config = None
        self.metadata = None
        self.load_artifacts()

    def load_artifacts(self):
        """Loads model, pipeline, and configs into memory."""
        try:
            if MODEL_PATH.exists() and PIPELINE_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
                self.pipeline = joblib.load(PIPELINE_PATH)
            
            if FEATURE_CONFIG_PATH.exists():
                with open(FEATURE_CONFIG_PATH, "r") as f:
                    self.feature_config = json.load(f)
                    
            if METADATA_PATH.exists():
                with open(METADATA_PATH, "r") as f:
                    self.metadata = json.load(f)
        except Exception as e:
            print(f"[-] Warning: Failed to load ML artifacts: {e}")

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.pipeline is not None

    def predict_risk(self, df_row: pd.DataFrame) -> dict:
        """
        Runs ML prediction on a single prepared DataFrame row.
        Returns probabilities, risk level, and Explainable AI feature attributions.
        """
        if not self.is_ready:
            self.load_artifacts()
            if not self.is_ready:
                # Fallback heuristic calculation if model file is not yet generated
                return self._fallback_heuristic_prediction(df_row)

        try:
            # Transform input via scikit-learn ColumnTransformer
            X_proc = self.pipeline.transform(df_row)
            
            # Predict probabilities
            prob_matrix = self.model.predict_proba(X_proc)[0]
            
            # Classes are [0 (At-Risk/Failure), 1 (Success)]
            if len(prob_matrix) == 2:
                prob_failure = float(prob_matrix[0])
                prob_success = float(prob_matrix[1])
            else:
                prob_success = float(prob_matrix[0])
                prob_failure = 1.0 - prob_success

            failure_pct = round(prob_failure * 100.0, 1)
            success_pct = round(prob_success * 100.0, 1)

            risk_info = get_risk_level_info(prob_failure)
            model_version = self.metadata.get("model_version", "Trained_ML_v1.0") if self.metadata else "Trained_ML_v1.0"

            # Compute Explainable AI feature contributions
            attributions = self._compute_feature_attributions(df_row, X_proc)
            risk_factors = self._extract_key_risk_factors(df_row, attributions)

            return {
                "success_probability": success_pct,
                "failure_probability": failure_pct,
                "risk_level": risk_info["level"],
                "risk_badge": risk_info["badge_class"],
                "risk_color": risk_info["color"],
                "text_color": risk_info.get("text_color", ""),
                "model_version": model_version,
                "shap_values": attributions,
                "risk_factors": risk_factors
            }
        except Exception as e:
            print(f"[-] Prediction error: {e}. Using fallback calculation.")
            return self._fallback_heuristic_prediction(df_row)

    def _compute_feature_attributions(self, df_row: pd.DataFrame, X_proc: np.ndarray) -> list:
        """
        Calculates feature attributions. Uses model weights/SHAP logic to attribute
        what increased or decreased failure risk.
        """
        attributions = []
        processed_feature_names = self.feature_config.get("processed_feature_names", []) if self.feature_config else []

        try:
            # If Linear / LogisticRegression model
            if hasattr(self.model, "coef_"):
                # Negative coefficient in class 1 means higher value increases failure (class 0)
                coefs = self.model.coef_[0]
                contributions = -(X_proc[0] * coefs)  # Positive contribution means pushes toward failure
                
                for idx, val in enumerate(contributions):
                    feat_name = processed_feature_names[idx] if idx < len(processed_feature_names) else f"Feature_{idx}"
                    clean_name = feat_name.split("__")[-1]
                    attributions.append({
                        "feature": clean_name,
                        "label": FEATURE_LABELS.get(clean_name, clean_name.replace("_", " ").title()),
                        "impact": round(float(val), 3),
                        "direction": "Increases Risk" if val > 0.05 else ("Decreases Risk" if val < -0.05 else "Neutral")
                    })
            # Tree / Ensemble models
            elif hasattr(self.model, "feature_importances_"):
                importances = self.model.feature_importances_
                for idx, imp in enumerate(importances):
                    feat_name = processed_feature_names[idx] if idx < len(processed_feature_names) else f"Feature_{idx}"
                    clean_name = feat_name.split("__")[-1]
                    attributions.append({
                        "feature": clean_name,
                        "label": FEATURE_LABELS.get(clean_name, clean_name.replace("_", " ").title()),
                        "impact": round(float(imp), 3),
                        "direction": "Important Factor"
                    })
        except Exception as e:
            print(f"[-] Attribution error: {e}")

        # Sort by absolute impact magnitude
        attributions = sorted(attributions, key=lambda x: abs(x["impact"]), reverse=True)
        return attributions[:10]

    def _extract_key_risk_factors(self, df_row: pd.DataFrame, attributions: list) -> list:
        """
        Translates numerical attributions and project metrics into clear human-understandable
        bullet points for students and faculty.
        """
        factors = []
        row = df_row.iloc[0]

        # 1. Testing lag
        testing_pct = float(row.get("testing_percentage", 0))
        prog_pct = float(row.get("progress_percentage", 0))
        if testing_pct < 35 or (prog_pct - testing_pct > 25):
            factors.append({
                "feature": "testing_percentage",
                "feature_label": f"Testing is only {testing_pct:.0f}% (Testing lag behind {prog_pct:.0f}% progress)",
                "impact_score": 8.5,
                "direction": "Risk Driver"
            })

        # 2. Delayed tasks
        delayed_tasks = int(row.get("delayed_tasks", 0))
        total_tasks = int(row.get("total_tasks", 10))
        if delayed_tasks >= 2 or (delayed_tasks / max(1, total_tasks) > 0.15):
            factors.append({
                "feature": "delayed_tasks",
                "feature_label": f"{delayed_tasks} out of {total_tasks} tasks are currently delayed",
                "impact_score": 9.0,
                "direction": "Risk Driver"
            })

        # 3. Schedule pressure and deadline
        days_remaining = int(row.get("days_remaining", 30))
        remaining_work = int(row.get("remaining_work", 5))
        if days_remaining <= 14 and remaining_work > 3:
            factors.append({
                "feature": "schedule_pressure",
                "feature_label": f"High schedule pressure: {remaining_work} tasks remaining with only {days_remaining} days left",
                "impact_score": 8.0,
                "direction": "Risk Driver"
            })

        # 4. Bugs
        bugs = int(row.get("bugs", 0))
        if bugs >= 4:
            factors.append({
                "feature": "bugs",
                "feature_label": f"{bugs} unresolved software bugs reported",
                "impact_score": 7.5,
                "direction": "Risk Driver"
            })

        # 5. Documentation
        doc_pct = float(row.get("documentation_percentage", 0))
        if doc_pct < 30 and prog_pct > 50:
            factors.append({
                "feature": "documentation_percentage",
                "feature_label": f"Documentation is lagging at {doc_pct:.0f}%",
                "impact_score": 6.5,
                "direction": "Risk Driver"
            })

        # 6. Collaboration
        collab = float(row.get("collaboration_rating", 4.0))
        if collab <= 3.0:
            factors.append({
                "feature": "collaboration_rating",
                "feature_label": f"Team collaboration rating is low ({collab:.1f}/5.0)",
                "impact_score": 6.0,
                "direction": "Risk Driver"
            })

        # If no critical negative factors found, show positive progress driver
        if not factors:
            factors.append({
                "feature": "progress_percentage",
                "feature_label": f"Solid project pacing ({prog_pct:.0f}% completed with minimal delays)",
                "impact_score": 9.0,
                "direction": "Positive Driver"
            })

        return factors

    def _fallback_heuristic_prediction(self, df_row: pd.DataFrame) -> dict:
        """Safe fallback if model is compiling."""
        row = df_row.iloc[0]
        prog = float(row.get("progress_percentage", 50))
        test = float(row.get("testing_percentage", 30))
        delays = int(row.get("delayed_tasks", 0))
        
        failure_score = max(0.05, min(0.95, (1.0 - (prog / 100) * 0.5 - (test / 100) * 0.3 + (delays * 0.1))))
        failure_pct = round(failure_score * 100, 1)
        success_pct = round((1.0 - failure_score) * 100, 1)
        risk_info = get_risk_level_info(failure_score)

        return {
            "success_probability": success_pct,
            "failure_probability": failure_pct,
            "risk_level": risk_info["level"],
            "risk_badge": risk_info["badge_class"],
            "risk_color": risk_info["color"],
            "text_color": risk_info.get("text_color", ""),
            "model_version": "Heuristic_Fallback_v1.0",
            "shap_values": [],
            "risk_factors": [
                {
                    "feature": "progress_percentage",
                    "feature_label": f"Progress at {prog}% with {delays} delayed tasks",
                    "impact_score": 7.0,
                    "direction": "Risk Factor"
                }
            ]
        }


# Global singleton instance
_ml_service_instance = None

def get_ml_service() -> MLService:
    global _ml_service_instance
    if _ml_service_instance is None:
        _ml_service_instance = MLService()
    return _ml_service_instance
