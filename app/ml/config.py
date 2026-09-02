"""ML configuration, features definitions, and risk level mapping."""

# Core Feature Definitions
NUMERICAL_FEATURES = [
    "team_size",
    "total_tasks",
    "completed_tasks",
    "pending_tasks",
    "delayed_tasks",
    "progress_percentage",
    "testing_percentage",
    "documentation_percentage",
    "presentation_percentage",
    "bugs",
    "technologies_count",
    "previous_evaluation_score",
    "days_remaining",
    "collaboration_rating",
    # Engineered features
    "completion_ratio",
    "delay_ratio",
    "remaining_work",
    "schedule_pressure",
    "test_coverage_gap",
    "doc_coverage_gap",
    "bug_density"
]

CATEGORICAL_FEATURES = [
    "technology_difficulty",  # Easy, Medium, Hard
    "project_domain"          # Web, Mobile, AI/ML, IoT, Cloud, Blockchain, Cybersecurity, Other
]

ALL_MODEL_FEATURES = NUMERICAL_FEATURES + CATEGORICAL_FEATURES

TARGET_FEATURE = "final_result"  # 1 = Successful, 0 = Failed / At Risk

# Risk Categories based on Failure Probability (0.0 to 1.0)
RISK_LEVEL_MAP = [
    {"level": "LOW", "min": 0.0, "max": 0.20, "color": "success", "badge_class": "bg-success", "text_color": "text-emerald-600"},
    {"level": "MODERATE", "min": 0.2001, "max": 0.40, "color": "warning", "badge_class": "bg-warning text-dark", "text_color": "text-amber-500"},
    {"level": "HIGH", "min": 0.4001, "max": 0.60, "color": "orange", "badge_class": "bg-orange-500 text-white", "text_color": "text-orange-500"},
    {"level": "CRITICAL", "min": 0.6001, "max": 1.00, "color": "danger", "badge_class": "bg-danger", "text_color": "text-red-600"},
]

def get_risk_level_info(failure_probability: float) -> dict:
    """Returns risk level label and styling metadata for a given failure probability."""
    prob = max(0.0, min(1.0, float(failure_probability)))
    for item in RISK_LEVEL_MAP:
        if item["min"] <= prob <= item["max"]:
            return item
    return RISK_LEVEL_MAP[-1]
