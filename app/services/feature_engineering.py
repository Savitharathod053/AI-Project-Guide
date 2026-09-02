"""Feature engineering and automated metrics calculation service."""
from datetime import date, datetime
import pandas as pd
import numpy as np


def compute_derived_features(
    total_tasks: int,
    completed_tasks: int,
    delayed_tasks: int,
    progress_percentage: float,
    testing_percentage: float,
    documentation_percentage: float,
    bugs: int,
    start_date: date,
    deadline: date,
    current_date: date = None
) -> dict:
    """
    Calculates derived features with rigorous zero-division safeguards.
    """
    if current_date is None:
        current_date = date.today()

    raw_total = int(total_tasks or 0)
    raw_completed = int(completed_tasks or 0)
    remaining_work = max(0, raw_total - raw_completed)

    # Normalize inputs for ratio denominators
    total_tasks = max(1, raw_total)
    completed_tasks = max(0, min(total_tasks, raw_completed))
    delayed_tasks = max(0, int(delayed_tasks or 0))
    bugs = max(0, int(bugs or 0))
    progress_pct = max(0.0, min(100.0, float(progress_percentage or 0.0)))
    testing_pct = max(0.0, min(100.0, float(testing_percentage or 0.0)))
    doc_pct = max(0.0, min(100.0, float(documentation_percentage or 0.0)))

    # Compute timeline days
    if isinstance(deadline, (datetime,)):
        deadline = deadline.date()
    if isinstance(start_date, (datetime,)):
        start_date = start_date.date()
    if isinstance(current_date, (datetime,)):
        current_date = current_date.date()

    days_remaining = max(0, (deadline - current_date).days)
    total_duration_days = max(1, (deadline - start_date).days)

    # Derived ratios
    completion_ratio = round(completed_tasks / total_tasks, 4) if raw_total > 0 else 0.0
    delay_ratio = round(delayed_tasks / total_tasks, 4) if raw_total > 0 else 0.0
    
    # Schedule pressure: remaining tasks per day remaining
    schedule_pressure = round(remaining_work / max(1, days_remaining), 4) if remaining_work > 0 else 0.0

    # Quality and gap metrics
    test_coverage_gap = max(0.0, round(progress_pct - testing_pct, 2))
    doc_coverage_gap = max(0.0, round(progress_pct - doc_pct, 2))
    bug_density = round(bugs / max(1, completed_tasks), 4)

    return {
        "completion_ratio": completion_ratio,
        "delay_ratio": delay_ratio,
        "remaining_work": remaining_work,
        "days_remaining": days_remaining,
        "total_duration_days": total_duration_days,
        "schedule_pressure": schedule_pressure,
        "test_coverage_gap": test_coverage_gap,
        "doc_coverage_gap": doc_coverage_gap,
        "bug_density": bug_density
    }


def prepare_feature_row(project, progress, current_date: date = None) -> pd.DataFrame:
    """
    Transforms a Project and ProjectProgress database model instance into
    a single-row pandas DataFrame compatible with the ML pipeline.
    """
    derived = compute_derived_features(
        total_tasks=progress.total_tasks,
        completed_tasks=progress.completed_tasks,
        delayed_tasks=progress.delayed_tasks,
        progress_percentage=progress.progress_percentage,
        testing_percentage=progress.testing_percentage,
        documentation_percentage=progress.documentation_percentage,
        bugs=progress.bugs,
        start_date=project.start_date,
        deadline=project.deadline,
        current_date=current_date
    )

    row = {
        "team_size": int(project.team_size or 1),
        "total_tasks": int(progress.total_tasks),
        "completed_tasks": int(progress.completed_tasks),
        "pending_tasks": int(progress.pending_tasks),
        "delayed_tasks": int(progress.delayed_tasks),
        "progress_percentage": float(progress.progress_percentage),
        "testing_percentage": float(progress.testing_percentage),
        "documentation_percentage": float(progress.documentation_percentage),
        "presentation_percentage": float(progress.presentation_percentage),
        "bugs": int(progress.bugs),
        "technologies_count": int(project.technologies_count or 1),
        "previous_evaluation_score": float(progress.evaluation_score or 70.0),
        "days_remaining": derived["days_remaining"],
        "collaboration_rating": float(progress.collaboration_rating or 4.0),
        "completion_ratio": derived["completion_ratio"],
        "delay_ratio": derived["delay_ratio"],
        "remaining_work": derived["remaining_work"],
        "schedule_pressure": derived["schedule_pressure"],
        "test_coverage_gap": derived["test_coverage_gap"],
        "doc_coverage_gap": derived["doc_coverage_gap"],
        "bug_density": derived["bug_density"],
        "technology_difficulty": str(project.technology_difficulty or "Medium"),
        "project_domain": str(project.domain or "Web Development")
    }

    return pd.DataFrame([row])


def prepare_raw_dict_feature_row(data: dict) -> pd.DataFrame:
    """
    Transforms raw dictionary input (e.g. from What-If form or REST API)
    into a single-row DataFrame.
    """
    # Parse dates or days_remaining
    start_date = data.get("start_date")
    deadline = data.get("deadline")
    current_date = data.get("current_date") or date.today()

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    elif not start_date:
        start_date = date.today()

    if isinstance(deadline, str):
        deadline = datetime.strptime(deadline, "%Y-%m-%d").date()
    elif not deadline:
        deadline = date.today()

    total_tasks = int(data.get("total_tasks", 10))
    completed_tasks = int(data.get("completed_tasks", 0))
    pending_tasks = int(data.get("pending_tasks", max(0, total_tasks - completed_tasks)))
    delayed_tasks = int(data.get("delayed_tasks", 0))
    progress_pct = float(data.get("progress_percentage", round((completed_tasks / max(1, total_tasks)) * 100, 1)))
    testing_pct = float(data.get("testing_percentage", 0.0))
    doc_pct = float(data.get("documentation_percentage", 0.0))
    presentation_pct = float(data.get("presentation_percentage", 0.0))
    bugs = int(data.get("bugs", 0))

    derived = compute_derived_features(
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        delayed_tasks=delayed_tasks,
        progress_percentage=progress_pct,
        testing_percentage=testing_pct,
        documentation_percentage=doc_pct,
        bugs=bugs,
        start_date=start_date,
        deadline=deadline,
        current_date=current_date
    )

    # If explicit days_remaining provided in dict (e.g., in simulator slider)
    if "days_remaining" in data and data["days_remaining"] is not None:
        derived["days_remaining"] = max(0, int(data["days_remaining"]))
        derived["schedule_pressure"] = round(derived["remaining_work"] / max(1, derived["days_remaining"]), 4)

    row = {
        "team_size": int(data.get("team_size", 1)),
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "delayed_tasks": delayed_tasks,
        "progress_percentage": progress_pct,
        "testing_percentage": testing_pct,
        "documentation_percentage": doc_pct,
        "presentation_percentage": presentation_pct,
        "bugs": bugs,
        "technologies_count": int(data.get("technologies_count", 1)),
        "previous_evaluation_score": float(data.get("previous_evaluation_score", 70.0)),
        "days_remaining": derived["days_remaining"],
        "collaboration_rating": float(data.get("collaboration_rating", 4.0)),
        "completion_ratio": derived["completion_ratio"],
        "delay_ratio": derived["delay_ratio"],
        "remaining_work": derived["remaining_work"],
        "schedule_pressure": derived["schedule_pressure"],
        "test_coverage_gap": derived["test_coverage_gap"],
        "doc_coverage_gap": derived["doc_coverage_gap"],
        "bug_density": derived["bug_density"],
        "technology_difficulty": str(data.get("technology_difficulty", "Medium")),
        "project_domain": str(data.get("project_domain", "Web Development"))
    }

    return pd.DataFrame([row])
