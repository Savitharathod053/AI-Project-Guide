"""
TESTS FOR SMART RESOURCE FINDER & VERIFICATION SYSTEM
=====================================================
Tests Gemini project resource analysis, official resource directory resolution,
URL validation, contextual AI tool recommendations, task-resource mapping,
and secure role-isolated API endpoints.
"""

from datetime import date, timedelta
import pytest
from app import create_app
from app.models import db, User, Project, Task, ProjectResource, AIRecommendation
from app.services.resource_finder_service import get_resource_finder_service, OFFICIAL_RESOURCES_CATALOG


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


def test_resource_finder_service_analysis():
    """Test project analysis and structured requirements identification."""
    service = get_resource_finder_service()
    title = "Real-Time Air Pollution & Smog Prediction System"
    desc = "A web dashboard predicting daily PM2.5 and AQI levels using machine learning regression models."

    result = service.analyze_project_requirements(
        title=title,
        description=desc,
        domain="Machine Learning & AI",
        technologies="Python, Flask, Scikit-Learn, PostgreSQL",
        objective="Forecast local city air pollution index."
    )

    assert isinstance(result, dict)
    assert result.get("is_software") is True
    assert "resources_needed" in result
    assert len(result["resources_needed"]) >= 1

    # Verify resource fields schema
    res_item = result["resources_needed"][0]
    assert "type" in res_item
    assert "purpose" in res_item
    assert "description" in res_item
    assert "search_query" in res_item
    # Verify no fake generated URLs in Gemini output
    assert "url" not in res_item or not res_item.get("url")


def test_resource_verification_and_catalog_match():
    """Test matching against known official catalog and URL verification."""
    service = get_resource_finder_service()
    
    mock_analysis = {
        "resources_needed": [
            {
                "type": "api",
                "category": "Weather",
                "suggested_name": "Open-Meteo Weather API",
                "purpose": "Hourly weather and temperature observations",
                "description": "Required as predictive input.",
                "search_query": "official free weather API real time historical data"
            },
            {
                "type": "dataset",
                "category": "Weather",
                "suggested_name": "Historical Climate Dataset",
                "purpose": "10-year historical weather data",
                "description": "Used to train machine learning models.",
                "search_query": "historical weather dataset CSV download"
            }
        ]
    }

    verified = service.resolve_and_verify_resources(
        analysis=mock_analysis,
        project_title="Weather & Climate Predictor",
        project_domain="Machine Learning & AI"
    )

    assert len(verified) >= 2
    for item in verified:
        assert item["resource_name"]
        assert item["resource_type"] in ("api", "dataset", "ai_tool")
        assert item["verification_status"] in ("Verified", "Official Source", "Community Source")
        # Ensure all official URLs are valid http/https
        if item["official_url"]:
            assert item["official_url"].startswith("http://") or item["official_url"].startswith("https://")
        if item["documentation_url"]:
            assert item["documentation_url"].startswith("http://") or item["documentation_url"].startswith("https://")


def test_contextual_ai_tool_recommendations_and_prompts(test_app):
    """Test AI tool advisor recommends contextual tools with student project specifics."""
    with test_app.app_context():
        u = User(name="Dev Student", email="dev@college.edu", role="student")
        u.set_password("pass123")
        db.session.add(u)
        db.session.commit()

        p = Project(
            owner_id=u.id,
            project_name="Autonomous Drone Fleet Tracking Platform",
            description="IoT platform tracking drone GPS coordinates and telemetry data.",
            domain="Internet of Things (IoT)",
            technologies="Python, Flask, MQTT, PostgreSQL, React",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(p)
        db.session.commit()

        service = get_resource_finder_service()
        tools = service.generate_ai_tool_recommendations(p)

        assert len(tools) >= 5
        purposes = [t["purpose"] for t in tools]
        assert any("Research" in purp for purp in purposes)
        assert any("Coding" in purp for purp in purposes)
        assert any("UI/UX" in purp for purp in purposes)
        assert any("Database" in purp for purp in purposes)
        assert any("Testing" in purp for purp in purposes)

        # Contextual prompt contains project specifics
        coding_tool = next(t for t in tools if "Coding" in t["purpose"])
        assert "Autonomous Drone Fleet Tracking Platform" in coding_tool["generated_prompt"]
        assert "Python" in coding_tool["generated_prompt"]


def test_analyze_and_store_project_resources_deduplication(test_app, monkeypatch):
    """Test storing resources in database and avoiding duplicate records on refresh."""
    with test_app.app_context():
        u = User(name="Alice Dev", email="alice_dev@college.edu", role="student")
        u.set_password("pass123")
        db.session.add(u)
        db.session.commit()

        p = Project(
            owner_id=u.id,
            project_name="Campus Attendance with Voice Recognition",
            description="Student attendance roll-call using acoustic speech recognition.",
            domain="Machine Learning & AI",
            technologies="Python, Flask, Whisper, PostgreSQL",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=45)
        )
        db.session.add(p)
        db.session.commit()

        t1 = Task(
            project_id=p.id,
            title="Integrate Voice Recognition Model",
            category="Machine Learning",
            description="Connect speech recognition library for audio processing."
        )
        t2 = Task(
            project_id=p.id,
            title="Design Database Schema for Attendance",
            category="Database",
            description="Create tables for courses and daily attendance."
        )
        db.session.add_all([t1, t2])
        db.session.commit()

        service = get_resource_finder_service()
        # Mock Gemini call to guarantee deterministic offline execution without network latency
        monkeypatch.setattr(service, "_call_gemini_api", lambda *args, **kwargs: None)
        
        # 1st run
        res1 = service.analyze_and_store_project_resources(p, [t1, t2])
        assert res1["status"] == "success"
        initial_count = p.resources.count()
        assert initial_count > 0

        # Verify task-resource mapping
        whisper_res = ProjectResource.query.filter_by(project_id=p.id).filter(
            ProjectResource.resource_name.like("%Whisper%")
        ).first()
        if whisper_res:
            assert whisper_res.task_id == t1.id

        # 2nd run (refresh) - should not duplicate
        res2 = service.analyze_and_store_project_resources(p, [t1, t2])
        assert res2["status"] == "success"
        after_refresh_count = p.resources.count()
        assert after_refresh_count == initial_count


def test_api_resources_endpoints_and_project_isolation(test_app, client):
    """Test REST API endpoints for resources with strict student role isolation."""
    with test_app.app_context():
        s1 = User(name="Student S1", email="s1_res@college.edu", role="student")
        s1.set_password("pass123")
        s2 = User(name="Student S2", email="s2_res@college.edu", role="student")
        s2.set_password("pass123")
        db.session.add_all([s1, s2])
        db.session.commit()

        p1 = Project(
            owner_id=s1.id,
            project_name="Student 1 Solar Energy Forecast",
            description="Solar panel output forecasting with machine learning.",
            domain="Data Science",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=30)
        )
        db.session.add(p1)
        db.session.commit()
        p1_id = p1.id

        # Seed 1 resource for p1
        r = ProjectResource(
            project_id=p1.id,
            resource_name="Open-Meteo Solar API",
            resource_type="api",
            purpose="Solar radiation data",
            official_url="https://open-meteo.com/",
            documentation_url="https://open-meteo.com/en/docs",
            verification_status="Verified"
        )
        db.session.add(r)
        db.session.commit()

    # Login as s2 (attacker / unauthorized student)
    client.post("/auth/login", data={"email": "s2_res@college.edu", "password": "pass123"}, follow_redirects=True)

    # s2 tries to access s1's resources -> 403 Forbidden
    res = client.get(f"/api/projects/{p1_id}/resources")
    assert res.status_code == 403

    # Logout and login as s1 (authorized student)
    client.get("/auth/logout", follow_redirects=True)
    client.post("/auth/login", data={"email": "s1_res@college.edu", "password": "pass123"}, follow_redirects=True)

    # s1 accesses own resources -> 200 OK
    res = client.get(f"/api/projects/{p1_id}/resources")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "success"
    assert json_data["count"] >= 1
    assert json_data["resources"][0]["resource_name"] == "Open-Meteo Solar API"

    # Test analyze endpoint
    res_analyze = client.post(f"/api/projects/{p1_id}/resources/analyze")
    assert res_analyze.status_code == 200

    # Test AI tools recommend endpoint
    res_tools = client.post(f"/api/projects/{p1_id}/ai-tools/recommend")
    assert res_tools.status_code == 200
    tools_data = res_tools.get_json()
    assert len(tools_data["tools"]) >= 1

    # Test prompt generation endpoint
    res_prompt = client.post(f"/api/projects/{p1_id}/ai-tools/generate-prompt", json={
        "purpose": "Testing",
        "task_title": "Unit test solar forecasting logic"
    })
    assert res_prompt.status_code == 200
    prompt_data = res_prompt.get_json()
    assert "Student 1 Solar Energy Forecast" in prompt_data["prompt"]
    assert "Unit test solar forecasting logic" in prompt_data["prompt"]


def test_student_dashboard_smart_resources_tab(test_app, client):
    """Test project_detail template renders Smart Resources tab, cards, and buttons."""
    with test_app.app_context():
        student = User(name="Web Student", email="webstudent@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        p = Project(
            owner_id=student.id,
            project_name="AI Smart Project Guide",
            description="Automated project failure predictor and resource guide.",
            domain="Web Development",
            technologies="Python, Flask, SQLite",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(p)
        db.session.commit()
        p_id = p.id

    client.post("/auth/login", data={"email": "webstudent@college.edu", "password": "pass123"}, follow_redirects=True)
    res = client.get(f"/student/projects/{p_id}")
    assert res.status_code == 200
    # Verify Smart Resources tab and content exist
    assert b"Smart Resources" in res.data
    assert b"Recommended APIs" in res.data
    assert b"Recommended Datasets" in res.data
    assert b"Copy Prompt" in res.data
