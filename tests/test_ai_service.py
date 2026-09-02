"""AI Project Mentor and Generative Task Analysis Tests."""
import pytest
from app.services.ai_service import get_ai_service
from app.services.health_service import calculate_project_health_score
from app.models import Project, Task
from datetime import date, timedelta


def test_ai_project_analysis_and_task_generation():
    ai = get_ai_service()
    title = "AI Attendance System with Voice Commands"
    desc = "A web application where teachers take attendance by speaking student names, and students can login to see their attendance record."

    result = ai.analyze_project_and_generate_tasks(title, desc)
    assert isinstance(result, dict)
    assert "core_tasks" in result
    assert len(result["core_tasks"]) >= 5
    assert "project_summary" in result
    assert "suggested_technologies" in result

    # Verify task schema
    first_task = result["core_tasks"][0]
    assert "task_title" in first_task
    assert "category" in first_task
    assert "priority" in first_task
    assert "reason" in first_task


def test_duplicate_and_additional_task_evaluation():
    ai = get_ai_service()
    dummy_project = Project(
        project_name="AI Attendance System",
        description="Speech attendance system."
    )
    existing_tasks = [
        Task(title="Design Database Schema", category="Database"),
        Task(title="User Authentication Module", category="Backend")
    ]

    # Test duplicate detection
    res1 = ai.evaluate_additional_task(dummy_project, "Design database schema", existing_tasks)
    assert res1["is_duplicate"] is True

    # Test new unique task
    res2 = ai.evaluate_additional_task(dummy_project, "Add SMS notifications to parents", existing_tasks)
    assert res2["is_duplicate"] is False
    assert res2["category"] in ["Backend", "Frontend", "API", "Database"]


def test_missing_and_unnecessary_task_detection():
    ai = get_ai_service()
    dummy_project = Project(
        project_name="AI Image Classifier",
        description="Train machine learning model for image classification."
    )
    # Tasks lacking testing and documentation
    tasks = [
        Task(title="Dataset Download", category="Machine Learning"),
        Task(title="Train CNN Model", category="Machine Learning"),
        Task(title="Complex 3D Animated Landing Page Mascot", category="UI/UX", description="3D mascot animation")
    ]

    missing = ai.detect_missing_tasks(dummy_project, tasks)
    assert len(missing) > 0
    missing_titles = " ".join([m["title"].lower() for m in missing])
    assert "test" in missing_titles or "report" in missing_titles or "evaluat" in missing_titles

    unnecessary = ai.detect_unnecessary_tasks(dummy_project, tasks)
    assert len(unnecessary) > 0
    assert "animated" in unnecessary[0]["title"].lower() or "3d" in unnecessary[0]["title"].lower()


def test_blocker_troubleshooting():
    ai = get_ai_service()
    advice = ai.troubleshoot_blocker(
        "Database Connection",
        "psycopg2.OperationalError: could not connect to server: Connection refused"
    )
    assert len(advice) > 20
    assert "database" in advice.lower() or "connection" in advice.lower() or "port" in advice.lower()


def test_health_score_calculation():
    dummy_project = Project(
        project_name="Test Project",
        description="Test",
        start_date=date.today() - timedelta(days=20),
        deadline=date.today() + timedelta(days=40),
        initial_task_count=10
    )
    tasks = [
        Task(title="Task 1", category="Backend", status="Completed", is_core=True),
        Task(title="Task 2", category="Database", status="Completed", is_core=True),
        Task(title="Task 3", category="Testing", status="Completed", is_core=True),
        Task(title="Task 4", category="Documentation", status="In Progress", is_core=True),
        Task(title="Task 5", category="Frontend", status="Blocked", is_core=True),
    ]
    health = calculate_project_health_score(dummy_project, tasks)
    assert "health_score" in health
    assert 0.0 <= health["health_score"] <= 100.0
    assert health["task_completion"] == 60.0
    assert health["blocked_tasks"] < 100.0  # Penalized for 1 blocked task
