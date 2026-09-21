"""Comprehensive tests for Stage 1 Understanding, Stage 2 Requirement-to-Task Generation,
Validation filters, Domain-Specific Phase Generation, and Student Clarification Workflow.
"""
import json
import pytest
from app.services.ai_service import get_ai_service
from app.models import db, User, Project, Task
from app import create_app
from datetime import date, timedelta


@pytest.fixture
def test_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(test_app):
    return test_app.test_client()


@pytest.fixture
def ai_service():
    return get_ai_service()


def test_stage_1_project_understanding_detailed(ai_service):
    """Test Stage 1 deep analysis on a well-specified project."""
    title = "Campus Event Registration & Certificate Portal"
    desc = (
        "A responsive web application where students register for college technical workshops, "
        "organizers review attendee lists and mark attendance via QR codes, and faculty issue "
        "tamper-proof PDF certificates upon completion."
    )
    understanding = ai_service.analyze_project_understanding(
        title=title,
        description=desc,
        domain="Web Development",
        technologies_known="Flask, SQLite, Bootstrap",
        team_size=3,
        deadline_days=60
    )

    assert isinstance(understanding, dict)
    assert understanding.get("domain") in ["Web Development", "Full-Stack Web Application"]
    assert understanding.get("confidence_score", 0) >= 80.0
    assert understanding.get("clarification_required") is False
    assert len(understanding.get("required_features", [])) >= 2
    assert "technologies" in understanding
    assert understanding.get("core_objective") != ""


def test_stage_1_project_understanding_vague_clarification(ai_service):
    """Test Stage 1 flags vague descriptions and generates clarification questions."""
    title = "Attendance App"
    desc = "Make an attendance app."

    understanding = ai_service.analyze_project_understanding(
        title=title,
        description=desc,
        domain="Web Development",
        technologies_known="",
        team_size=1,
        deadline_days=30
    )

    assert isinstance(understanding, dict)
    assert understanding.get("confidence_score", 100) < 80.0
    assert understanding.get("clarification_required") is True
    assert len(understanding.get("clarification_questions", [])) >= 2


def test_stage_2_requirement_mapping_and_sources(ai_service):
    """Test Stage 2 maps tasks directly to requirement sources."""
    understanding = {
        "title": "Hospital Bed Allocation Tracker",
        "domain": "Web Development",
        "project_type": "Web Application",
        "core_objective": "Track vacant ICU and ward beds in real-time across regional clinics.",
        "project_summary": "Web platform for clinic bed tracking and ambulance coordination.",
        "required_features": [
            "Real-time ICU and ward bed vacancy monitoring",
            "Doctor triage intake queue and priority assignment",
            "Emergency ambulance bed reservation dispatch"
        ],
        "technologies": ["FastAPI", "PostgreSQL", "React", "WebSockets"],
        "confidence_score": 92.0,
        "clarification_required": False
    }

    plan = ai_service.generate_tasks_from_requirements(understanding, team_size=3, deadline_days=90)
    assert isinstance(plan, dict)
    phases = plan.get("phases", [])
    assert len(phases) >= 5

    all_tasks = []
    for ph in phases:
        for t in ph.get("tasks", []):
            all_tasks.append(t)

    assert len(all_tasks) >= 6
    # Verify requirement_source exists on all tasks
    for t in all_tasks:
        assert "requirement_source" in t
        assert t["requirement_source"] != ""
        assert "title" in t and len(t["title"]) > 5
        assert "category" in t
        assert "priority" in t


def test_validation_layer_contradiction_and_generic_filter(ai_service):
    """Test backend validation rejects generic tasks and filters out domain contradictions."""
    understanding = {
        "title": "Python Data Analysis CLI",
        "domain": "Data Science & Analytics",
        "project_type": "CLI Utility",
        "core_objective": "Parse server CSV logs and export summary charts.",
        "required_features": ["CSV log parsing", "Terminal summary tables", "PNG chart export"],
        "technologies": ["Python", "Pandas", "Matplotlib"]
    }

    # Synthesize raw tasks with intentional generic and contradictory tasks
    raw_tasks = [
        {"title": "Do coding", "description": "Write code", "category": "General", "priority": "High"},
        {"title": "Deploy to Google Play Store & iOS App Store", "description": "Mobile release", "category": "DevOps"},
        {"title": "Integrate Stripe payment checkout", "description": "Process credit cards", "category": "Backend"},
        {"title": "Train Deep Convolutional Neural Network on GPU", "description": "Train CNN", "category": "Machine Learning"},
        {"title": "Parse server CSV log files with Pandas", "description": "Implement log ingestion engine", "category": "Backend", "requirement_source": "CSV log parsing"}
    ]

    sanitized = ai_service.validate_and_sanitize_tasks(raw_tasks, understanding)

    titles = [t["title"].lower() for t in sanitized]
    # "Do coding" should either be rejected or rewritten to a specific task
    for tit in titles:
        assert "do coding" not in tit
        # Mobile app store, payment, and CNN model should be filtered out
        assert "google play store" not in tit
        assert "stripe" not in tit
        assert "convolutional neural network" not in tit

    # Legitimate log parsing task must remain
    assert any("parse server csv log" in tit for tit in titles)


def test_domain_specific_phases_generation(ai_service):
    """Test distinct domain project types produce appropriate domain-specific phases."""
    # 1. Machine Learning Project
    ml_understanding = {
        "title": "Solar Energy Output Predictor",
        "domain": "Machine Learning & AI",
        "project_type": "Machine Learning Pipeline",
        "core_objective": "Predict solar power output from weather metrics.",
        "required_features": ["Solar irradiance feature scaling", "XGBoost regression training"],
        "technologies": ["Python", "Scikit-Learn", "XGBoost"]
    }
    ml_plan = ai_service.generate_tasks_from_requirements(ml_understanding, team_size=2, deadline_days=60)
    ml_phase_names = [p["name"] for p in ml_plan.get("phases", [])]
    assert any("Data Preprocessing" in name or "Data Sourcing" in name for name in ml_phase_names)
    assert any("Model Architecture" in name or "Model Evaluation" in name for name in ml_phase_names)

    # 2. IoT Project
    iot_understanding = {
        "title": "Smart Soil Moisture & Irrigation Node",
        "domain": "Internet of Things (IoT)",
        "project_type": "Internet of Things (IoT)",
        "core_objective": "Automated greenhouse watering using capacitive soil sensors.",
        "required_features": ["ESP32 analog sensor polling", "Relay solenoid valve actuation"],
        "technologies": ["ESP32", "C++", "MQTT"]
    }
    iot_plan = ai_service.generate_tasks_from_requirements(iot_understanding, team_size=2, deadline_days=60)
    iot_phase_names = [p["name"] for p in iot_plan.get("phases", [])]
    assert any("Circuit Design" in name or "Architecture & Component" in name for name in iot_phase_names)
    assert any("Firmware" in name for name in iot_phase_names)


def test_project_clarification_and_approval_workflow(test_app, client):
    """Test end-to-end student flow: Vague project triggers clarification, answering generates plan, and approving roadmap."""
    with test_app.app_context():
        student = User(name="Charlie Student", email="charlie@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

    # Login
    client.post("/auth/login", data={"email": "charlie@college.edu", "password": "pass123"}, follow_redirects=True)

    # 1. Submit vague project (very brief description < 40 chars)
    res = client.post("/student/projects/new", data={
        "project_name": "Quick Chat",
        "description": "A quick chat.",
        "domain": "Web Development",
        "team_size": "2",
        "deadline": (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
    }, follow_redirects=False)

    # Should redirect to /clarify because description is very short
    assert res.status_code == 302
    assert "/clarify" in res.location

    # Extract project_id from redirect URL
    project_id = int(res.location.split("/projects/")[1].split("/clarify")[0])

    # 2. Visit Clarification page (GET)
    get_clarify = client.get(f"/student/projects/{project_id}/clarify")
    assert get_clarify.status_code == 200
    assert b"Clarification" in get_clarify.data

    # 3. Post answers to clarification questions
    post_clarify = client.post(f"/student/projects/{project_id}/clarify", data={
        "question_0": "WebSockets for real-time messaging and SQLite for message history",
        "question_1": "Students and project mentors with room invitation codes",
        "general_notes": "Include end-to-end typing indicators and read receipts"
    }, follow_redirects=False)

    assert post_clarify.status_code == 302
    assert f"/projects/{project_id}/review-tasks" in post_clarify.location

    # 4. Visit review tasks page
    review_res = client.get(f"/student/projects/{project_id}/review-tasks")
    assert review_res.status_code == 200
    assert b"Mapped Requirement:" in review_res.data
    assert b"Approve Roadmap &amp; Open Workspace" in review_res.data or b"Approve Roadmap & Open Workspace" in review_res.data

    # 5. Approve Roadmap (POST)
    approve_res = client.post(f"/student/projects/{project_id}/approve-roadmap", follow_redirects=False)
    assert approve_res.status_code == 302
    assert f"/projects/{project_id}" in approve_res.location

    # Verify project is marked approved in DB
    with test_app.app_context():
        p = db.session.get(Project, project_id)
        assert p.plan_approved is True
        tasks = p.tasks.all()
        assert len(tasks) >= 5
        assert any(t.requirement_source != "" for t in tasks)
