"""
PROJECT HEALTH SCORE & METRICS CALCULATION SERVICE
==================================================
Transparently computes 0-100 Project Health Scores and scope creep indicators.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, List


def calculate_project_health_score(project, tasks: List[Any]) -> Dict[str, Any]:
    """
    Calculates transparent 0-100 Project Health Score with component breakdown.
    """
    total = len(tasks)
    today = date.today()
    dead_d = project.deadline if project and project.deadline else (today + timedelta(days=90))
    days_rem = max(0, (dead_d - today).days)

    if total == 0:
        return {
            "health_score": 75.0,
            "task_completion": 0.0,
            "schedule": 100.0,
            "testing": 0.0,
            "blocked_tasks": 100.0,
            "core_functionality": 0.0,
            "documentation": 0.0,
            "scope_expansion": 0,
            "is_scope_creep": False,
            "time_percentage": 0.0,
            "days_remaining": days_rem
        }

    completed = sum(1 for t in tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "Completed")
    blocked = sum(1 for t in tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "Blocked")
    
    core_tasks = [t for t in tasks if (t.is_core if hasattr(t, 'is_core') else t.get('is_core', True))]
    completed_core = sum(1 for t in core_tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "Completed")
    
    testing_tasks = [t for t in tasks if (t.category if hasattr(t, 'category') else t.get('category')) == "Testing"]
    completed_testing = sum(1 for t in testing_tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "Completed")
    
    doc_tasks = [t for t in tasks if (t.category if hasattr(t, 'category') else t.get('category')) == "Documentation"]
    completed_doc = sum(1 for t in doc_tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "Completed")

    # 1. Task Completion (0-100)
    score_task_comp = round((completed / max(1, total)) * 100.0, 1)

    # 2. Schedule Pacing (0-100)
    today = date.today()
    start_d = project.start_date
    dead_d = project.deadline
    total_days = max(1, (dead_d - start_d).days)
    elapsed_days = max(0, (today - start_d).days)
    time_pct = min(100.0, (elapsed_days / total_days) * 100.0)

    # If time % is much higher than completion %, schedule score drops
    schedule_lag = max(0.0, time_pct - score_task_comp)
    score_schedule = max(10.0, round(100.0 - (schedule_lag * 1.2), 1))

    # 3. Testing (0-100)
    if testing_tasks:
        score_testing = round((completed_testing / len(testing_tasks)) * 100.0, 1)
    else:
        score_testing = 30.0  # Base penalty if no explicit testing tasks

    # 4. Blocked Tasks (0-100)
    score_blocked = max(0.0, round(100.0 - (blocked * 25.0), 1))

    # 5. Core Functionality (0-100)
    if core_tasks:
        score_core = round((completed_core / len(core_tasks)) * 100.0, 1)
    else:
        score_core = score_task_comp

    # 6. Documentation (0-100)
    if doc_tasks:
        score_doc = round((completed_doc / len(doc_tasks)) * 100.0, 1)
    else:
        score_doc = 40.0

    # Composite Health Score
    overall = (
        (score_task_comp * 0.25) +
        (score_schedule * 0.20) +
        (score_testing * 0.20) +
        (score_blocked * 0.15) +
        (score_core * 0.10) +
        (score_doc * 0.10)
    )
    overall = round(max(0.0, min(100.0, overall)), 1)

    # Scope Expansion
    initial_count = project.initial_task_count or total
    scope_expansion = max(0, total - initial_count)

    return {
        "health_score": overall,
        "task_completion": score_task_comp,
        "schedule": score_schedule,
        "testing": score_testing,
        "blocked_tasks": score_blocked,
        "core_functionality": score_core,
        "documentation": score_doc,
        "time_percentage": round(time_pct, 1),
        "days_remaining": max(0, (dead_d - today).days),
        "scope_expansion": scope_expansion,
        "is_scope_creep": scope_expansion >= 5
    }
