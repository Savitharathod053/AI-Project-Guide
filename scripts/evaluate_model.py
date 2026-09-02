"""
MODEL EVALUATION AND DIAGNOSTICS SCRIPT
=======================================
Loads the saved trained model and pipeline and runs evaluation on the test set,
displaying detailed classification metrics, confusion matrices, and feature importances.
"""

import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "trained_model.pkl"
PIPELINE_PATH = BASE_DIR / "models" / "pipeline.pkl"
METADATA_PATH = BASE_DIR / "models" / "model_metadata.json"
DATA_PATH = BASE_DIR / "data" / "raw" / "demo_student_projects.csv"
FEATURE_CONFIG_PATH = BASE_DIR / "models" / "feature_config.json"


def evaluate():
    print("[*] Evaluating saved model artifacts...")
    if not (MODEL_PATH.exists() and PIPELINE_PATH.exists()):
        print("[-] Model artifacts missing. Run scripts/train_model.py first.")
        return

    model = joblib.load(MODEL_PATH)
    pipeline = joblib.load(PIPELINE_PATH)

    with open(FEATURE_CONFIG_PATH, "r") as f:
        feature_config = json.load(f)

    with open(METADATA_PATH, "r") as f:
        metadata = json.load(f)

    df = pd.read_csv(DATA_PATH)
    X = df[feature_config["all_input_features"]]
    y = df[feature_config["target_feature"]]

    _, X_test, _, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    X_test_proc = pipeline.transform(X_test)
    y_pred = model.predict(X_test_proc)
    y_prob = model.predict_proba(X_test_proc)[:, 1]

    print("\n=======================================================")
    print(f"ACTIVE MODEL: {metadata.get('model_name')}")
    print(f"TRAINED AT:   {metadata.get('training_date')}")
    print("=======================================================")
    print(f"ROC-AUC Score: {roc_auc_score(y_test, y_prob):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["At-Risk / Failed (0)", "Successful (1)"]))

    cm = confusion_matrix(y_test, y_pred)
    print("Confusion Matrix:")
    print(f"  True At-Risk correctly identified: {cm[0][0]}")
    print(f"  At-Risk missed (False Positive):  {cm[0][1]}")
    print(f"  Successful misclassified as risk: {cm[1][0]}")
    print(f"  True Successful identified:       {cm[1][1]}")


if __name__ == "__main__":
    evaluate()
