"""
MACHINE LEARNING TRAINING AND MODEL SELECTION PIPELINE
======================================================
Trains and evaluates:
1. Logistic Regression
2. Random Forest Classifier
3. XGBoost Classifier

Compares Accuracy, Precision, Recall (High-Risk/Class 0 and Class 1), F1, ROC-AUC, and Confusion Matrices.
Selects the best model and serializes:
- models/trained_model.pkl
- models/pipeline.pkl
- models/feature_config.json
- models/model_metadata.json
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

# Add parent directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.ml.config import NUMERICAL_FEATURES, CATEGORICAL_FEATURES, ALL_MODEL_FEATURES, TARGET_FEATURE

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "raw" / "demo_student_projects.csv"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def build_preprocessor() -> ColumnTransformer:
    """Builds a robust, reproducible scikit-learn ColumnTransformer."""
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])

    cat_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_pipeline, NUMERICAL_FEATURES),
            ("cat", cat_pipeline, CATEGORICAL_FEATURES)
        ],
        remainder="drop"
    )
    return preprocessor


def train_and_evaluate_all():
    print(f"[*] Loading training dataset from: {DATA_PATH}")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}. Run scripts/generate_demo_data.py first.")

    df = pd.read_csv(DATA_PATH)
    print(f"[+] Loaded {len(df)} records. Columns: {list(df.columns)}")

    # Features and Target
    X = df[ALL_MODEL_FEATURES]
    y = df[TARGET_FEATURE]

    # Stratified Train/Test Split (80% Train, 20% Test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"[+] Train shape: {X_train.shape}, Test shape: {X_test.shape}")

    # Build and fit preprocessor on training data only to prevent data leakage
    preprocessor = build_preprocessor()
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    # Extract transformed feature names
    cat_encoder = preprocessor.named_transformers_["cat"].named_steps["encoder"]
    cat_feature_names = list(cat_encoder.get_feature_names_out(CATEGORICAL_FEATURES))
    processed_feature_names = NUMERICAL_FEATURES + cat_feature_names

    models = {
        "LogisticRegression": LogisticRegression(
            C=1.0, max_iter=1000, random_state=42, class_weight="balanced"
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=150, max_depth=8, min_samples_split=4, random_state=42, class_weight="balanced"
        ),
        "XGBoost": XGBClassifier(
            n_estimators=150, max_depth=4, learning_rate=0.08, eval_metric="logloss",
            random_state=42
        )
    }

    results = {}
    fitted_models = {}

    print("\n" + "=" * 80)
    print("MODEL BENCHMARKING & EVALUATION RESULTS")
    print("=" * 80)

    for name, clf in models.items():
        print(f"\n--- Training: {name} ---")
        clf.fit(X_train_proc, y_train)
        fitted_models[name] = clf

        y_pred = clf.predict(X_test_proc)
        y_prob = clf.predict_proba(X_test_proc)[:, 1]  # Prob of success (class 1)
        y_prob_failure = 1.0 - y_prob                  # Prob of failure (class 0)

        acc = accuracy_score(y_test, y_pred)
        prec_success = precision_score(y_test, y_pred, pos_label=1)
        rec_success = recall_score(y_test, y_pred, pos_label=1)
        f1 = f1_score(y_test, y_pred, pos_label=1)
        
        # High risk / Failure recall (Target = 0)
        rec_failure = recall_score(y_test, y_pred, pos_label=0)
        prec_failure = precision_score(y_test, y_pred, pos_label=0)
        roc_auc = roc_auc_score(y_test, y_prob)
        cm = confusion_matrix(y_test, y_pred).tolist()

        results[name] = {
            "model_name": name,
            "accuracy": round(float(acc), 4),
            "precision_success": round(float(prec_success), 4),
            "recall_success": round(float(rec_success), 4),
            "precision_failure": round(float(prec_failure), 4),
            "recall_failure": round(float(rec_failure), 4),  # High-risk project recall
            "f1_score": round(float(f1), 4),
            "roc_auc": round(float(roc_auc), 4),
            "confusion_matrix": cm,
            "classification_report": classification_report(y_test, y_pred, target_names=["At-Risk (0)", "Successful (1)"], output_dict=True)
        }

        print(f"Accuracy:            {acc:.4f}")
        print(f"ROC-AUC:             {roc_auc:.4f}")
        print(f"F1-Score (Success):  {f1:.4f}")
        print(f"Recall (At-Risk 0):  {rec_failure:.4f}  <-- Crucial Early-Warning Metric")
        print(f"Precision (At-Risk): {prec_failure:.4f}")
        print(f"Confusion Matrix:\n{np.array(cm)}")

    # Model Selection Strategy:
    # We rank by a composite score favoring High-Risk Recall (0.5 weight) and ROC-AUC (0.5 weight)
    best_model_name = max(
        results.keys(),
        key=lambda m: (results[m]["recall_failure"] * 0.5 + results[m]["roc_auc"] * 0.5)
    )
    best_clf = fitted_models[best_model_name]
    best_metrics = results[best_model_name]

    print("\n" + "=" * 80)
    print(f"[*] SELECTED BEST MODEL: {best_model_name}")
    print(f"[*] High-Risk Recall: {best_metrics['recall_failure']:.4f}, ROC-AUC: {best_metrics['roc_auc']:.4f}, Accuracy: {best_metrics['accuracy']:.4f}")
    print("=" * 80)

    # Save Model Artifacts
    model_path = MODELS_DIR / "trained_model.pkl"
    pipeline_path = MODELS_DIR / "pipeline.pkl"
    feature_config_path = MODELS_DIR / "feature_config.json"
    metadata_path = MODELS_DIR / "model_metadata.json"

    joblib.dump(best_clf, model_path)
    joblib.dump(preprocessor, pipeline_path)

    feature_config = {
        "numerical_features": NUMERICAL_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "all_input_features": ALL_MODEL_FEATURES,
        "processed_feature_names": processed_feature_names,
        "target_feature": TARGET_FEATURE,
        "categories": {
            "technology_difficulty": ["Easy", "Medium", "Hard"],
            "project_domain": [
                "Web Development", "Mobile Applications", "Machine Learning & AI",
                "Internet of Things (IoT)", "Cloud Computing", "Cybersecurity",
                "Blockchain", "Data Science & Analytics", "Other"
            ]
        }
    }
    with open(feature_config_path, "w") as f:
        json.dump(feature_config, f, indent=2)

    metadata = {
        "model_name": best_model_name,
        "model_version": f"{best_model_name}_v1.0",
        "training_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
        "dataset_name": "demo_student_projects.csv",
        "dataset_disclaimer": "DEMO / SYNTHETIC DATA — NOT REAL STUDENT DATA",
        "total_samples": len(df),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "best_metrics": best_metrics,
        "all_benchmarked_models": results
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"[+] Serialized model -> {model_path}")
    print(f"[+] Serialized pipeline -> {pipeline_path}")
    print(f"[+] Serialized feature config -> {feature_config_path}")
    print(f"[+] Serialized metadata -> {metadata_path}")


if __name__ == "__main__":
    train_and_evaluate_all()
