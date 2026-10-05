"""
TEST SUITE: PROJECT INNOVATION & UNIQUENESS ANALYZER
====================================================
Tests the full innovation analysis workflow:
1. Student analyzer page loads properly.
2. Project submission succeeds and returns structured analysis.
3. Validation handles empty / whitespace project title.
4. API accepts properly structured JSON payload.
5. API rejects invalid / non-JSON payload.
6. Gemini response parsing works correctly with schema validation.
7. Graceful rule-based fallback triggers on AI error or malformed response.
8. Discovered external comparisons contain authentic GitHub and arXiv URLs.
9. Student access control: Student cannot view another student's private analysis (403).
10. History API returns correct analyses for current student.
11. Secure handling of API keys: no keys exposed in response payload or error messages.
12. Friendly error handling when external search or network fails.
"""

import json
from unittest.mock import patch, MagicMock
import pytest
from app import create_app
from app.models import db, User, Project, ProjectAnalysis
from app.services.uniqueness_analyzer_service import (
    UniquenessAnalyzerService,
    get_uniqueness_analyzer_service,
)


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
def setup_users(test_app):
    """Sets up two test students and a faculty user."""
    with test_app.app_context():
        s1 = User(name="Alice Student", email="alice@college.edu", role="student")
        s1.set_password("pass123")

        s2 = User(name="Bob Student", email="bob@college.edu", role="student")
        s2.set_password("pass123")

        f = User(name="Prof Smith", email="smith@college.edu", role="faculty")
        f.set_password("pass123")

        db.session.add_all([s1, s2, f])
        db.session.commit()

        # Seed an existing campus project for internal comparison
        p = Project(
            owner_id=s2.id,
            project_name="Smart Campus Waste Segregator",
            description="Automated waste classification using machine learning and sensors.",
            domain="Machine Learning & AI",
            technologies="Python, OpenCV, TensorFlow",
            deadline=p_date if (p_date := None) else __import__("datetime").date.today()
        )
        db.session.add(p)
        db.session.commit()

        return {"alice_id": s1.id, "bob_id": s2.id, "faculty_id": f.id}


# =============================================================================
# TEST 1: Page Loads Properly
# =============================================================================
def test_1_page_loads_properly(test_app, client, setup_users):
    client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)
    res = client.get("/student/project-analyzer")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Project Innovation &amp; Uniqueness Analyzer" in html or "Project Innovation & Uniqueness Analyzer" in html
    assert "AI Comparison Notice" in html


# =============================================================================
# TEST 2: Project Submission Succeeds
# =============================================================================
def test_2_project_submission_succeeds(test_app, client, setup_users):
    client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)

    payload = {
        "project_title": "Drone-Based Solar Panel Fault Detection",
        "problem_statement": "Manual inspection of solar farms is slow and dangerous.",
        "project_description": "An autonomous drone equipped with thermal imaging to detect hot-spot defects.",
        "proposed_solution": "Process thermal video in real-time with lightweight neural networks.",
        "main_features": "Waypoint navigation, thermal hotspot detection, instant PDF report generation",
        "technologies_used": "Python, PyTorch, ROS, DJI SDK",
        "target_users": "Solar power plant maintenance engineers"
    }

    res = client.post(
        "/api/project-analyzer/analyze",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "data" in data
    assert data["data"]["project_title"] == "Drone-Based Solar Panel Fault Detection"
    assert "differentiation_score" in data["data"]
    assert "report" in data["data"]
    assert "improvement_suggestions" in data["data"]["report"]


# =============================================================================
# TEST 3: Validation Handles Empty / Invalid Input
# =============================================================================
def test_3_validation_handles_empty_title(test_app, client, setup_users):
    client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)

    # Empty title
    payload = {"project_title": "   ", "project_description": "Some description"}
    res = client.post("/api/project-analyzer/analyze", data=json.dumps(payload), content_type="application/json")
    assert res.status_code == 400
    assert "Project title is required" in res.get_json()["message"]


# =============================================================================
# TEST 4: API Accepts Properly Structured JSON
# =============================================================================
def test_4_api_accepts_structured_json(test_app, client, setup_users):
    client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)

    payload = {
        "project_title": "IoT Smart Agriculture Soil Nutrient Monitor",
        "problem_statement": "Farmers overuse fertilizer without real-time soil data.",
        "project_description": "Probe sensors reading NPK levels and communicating via LoRaWAN.",
        "main_features": "Soil NPK sensor integration, LoRa gateway, mobile app recommendations",
        "technologies_used": "ESP32, LoRaWAN, Flutter, Node.js"
    }

    res = client.post("/api/project-analyzer/analyze", data=json.dumps(payload), content_type="application/json")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["data"]["differentiation_score"] >= 0


# =============================================================================
# TEST 5: API Rejects Invalid Non-JSON
# =============================================================================
def test_5_api_rejects_non_json(test_app, client, setup_users):
    client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)

    res = client.post(
        "/api/project-analyzer/analyze",
        data="just plain text, not json",
        content_type="text/plain"
    )
    assert res.status_code == 400
    assert "Invalid request" in res.get_json()["message"]


# =============================================================================
# TEST 6: Gemini Response Parsing Works Correctly
# =============================================================================
def test_6_gemini_response_parsing(test_app):
    with test_app.app_context():
        service = UniquenessAnalyzerService()

        mock_gemini_json = json.dumps({
            "project_summary": "Autonomous drone system for solar inspection.",
            "differentiation_score": 78,
            "innovation_level": "Good",
            "score_rationale": "Thermal imaging combined with edge ROS is technically challenging and distinctive.",
            "what_already_exists": ["Standard waypoint drone navigation", "Basic OpenCV image filtering"],
            "potentially_unique_aspects": ["Real-time thermal hotspot classification on edge hardware"],
            "similar_external_projects": [],
            "similar_internal_projects": [],
            "improvement_suggestions": [
                {
                    "title": "Edge Quantization",
                    "suggested_direction": "Quantize model to INT8 for Jetson",
                    "why_it_improves_uniqueness": "Enables true offline flight without telemetry dropouts.",
                    "implementation_hint": "Use TensorRT",
                    "difficulty": "Medium"
                }
            ],
            "final_verdict": "High potential capstone project.",
            "disclaimer": "AI-assisted evaluation."
        })

        with patch.object(service.ai_service, "_call_gemini_api", return_value=mock_gemini_json):
            service.ai_service.gemini_key = "dummy_key_for_test"
            result = service.analyze_project_with_ai(
                project_data={"project_title": "Test Drone", "technologies_used": "Python"},
                external_evidence=[],
                internal_comparisons=[]
            )

            assert result["differentiation_score"] == 78
            assert result["innovation_level"] == "Good"
            assert "Edge Quantization" in result["improvement_suggestions"][0]["title"]
            assert "AI-assisted" in result["disclaimer"]


# =============================================================================
# TEST 7: Graceful Fallback Triggers on Gemini Error / Malformed JSON
# =============================================================================
def test_7_fallback_triggers_on_gemini_error(test_app):
    with test_app.app_context():
        service = UniquenessAnalyzerService()

        # Simulate Gemini failure raising Exception or returning garbage
        with patch.object(service.ai_service, "_call_gemini_api", side_effect=RuntimeError("Gemini Quota Exceeded")):
            service.ai_service.gemini_key = "dummy_key"
            result = service.analyze_project_with_ai(
                project_data={
                    "project_title": "AI Attendance System",
                    "project_description": "Face recognition attendance system for classroom.",
                    "technologies_used": "Python, OpenCV"
                },
                external_evidence=[],
                internal_comparisons=[]
            )

            # Fallback must produce a valid structured report without crashing
            assert isinstance(result, dict)
            assert "differentiation_score" in result
            assert "innovation_level" in result
            assert len(result["improvement_suggestions"]) >= 2
            assert "disclaimer" in result


# =============================================================================
# TEST 8: External Comparison Results Contain Valid URLs
# =============================================================================
def test_8_external_results_contain_valid_urls(test_app):
    with test_app.app_context():
        service = UniquenessAnalyzerService()

        # Query real search endpoints or mock authentic sample responses
        queries = ["waste classification", "solar defect detection"]
        sample_ext = [
            {
                "source_type": "GitHub Repository",
                "title": "owner/waste-detector",
                "description": "Object detection model for waste segregation",
                "url": "https://github.com/owner/waste-detector",
                "query_used": "waste classification"
            },
            {
                "source_type": "Research Paper (arXiv)",
                "title": "Deep Learning for Automated Solar Panel Defect Detection",
                "description": "Paper analyzing photoluminescence images",
                "url": "https://arxiv.org/abs/2103.12345",
                "query_used": "solar defect detection"
            }
        ]

        report = service._generate_rule_based_report(
            project_data={"project_title": "Smart Sorter"},
            external_evidence=sample_ext,
            internal_comparisons=[]
        )

        for item in report["similar_external_projects"]:
            url = item["url"]
            assert url.startswith("https://github.com/") or url.startswith("https://arxiv.org/") or url.startswith("http://arxiv.org/")


# =============================================================================
# TEST 9: Student Cannot View Other Students' Private Project Analyses (403)
# =============================================================================
def test_9_student_access_control_403(test_app, client, setup_users):
    with test_app.app_context():
        # Create an analysis belonging to Bob (setup_users["bob_id"])
        bob_analysis = ProjectAnalysis(
            student_id=setup_users["bob_id"],
            project_title="Bob Private Project",
            input_hash="hash_bob_123",
            report_json=json.dumps({"differentiation_score": 60, "improvement_suggestions": []})
        )
        db.session.add(bob_analysis)
        db.session.commit()
        bob_analysis_id = bob_analysis.id

    # Log in as Alice
    client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)

    # Alice attempts to access Bob's analysis
    res = client.get(f"/api/project-analyzer/{bob_analysis_id}")
    assert res.status_code == 403
    data = res.get_json()
    assert "Unauthorized" in data["message"]


# =============================================================================
# TEST 10: History API Returns Correct Analyses for Current Student
# =============================================================================
def test_10_history_api_returns_student_records(test_app, client, setup_users):
    with test_app.app_context():
        # Create 2 analyses for Alice and 1 for Bob
        a1 = ProjectAnalysis(
            student_id=setup_users["alice_id"],
            project_title="Alice Project Alpha",
            input_hash="hash_alpha",
            differentiation_score=75,
            report_json=json.dumps({"score": 75})
        )
        a2 = ProjectAnalysis(
            student_id=setup_users["alice_id"],
            project_title="Alice Project Beta",
            input_hash="hash_beta",
            differentiation_score=82,
            report_json=json.dumps({"score": 82})
        )
        b1 = ProjectAnalysis(
            student_id=setup_users["bob_id"],
            project_title="Bob Secret App",
            input_hash="hash_bob",
            differentiation_score=40,
            report_json=json.dumps({"score": 40})
        )
        db.session.add_all([a1, a2, b1])
        db.session.commit()

    # Log in as Alice
    client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)

    res = client.get("/api/project-analyzer/history")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] == 2
    titles = [item["project_title"] for item in data["data"]]
    assert "Alice Project Alpha" in titles
    assert "Alice Project Beta" in titles
    assert "Bob Secret App" not in titles


# =============================================================================
# TEST 11: Secure Handling of API Keys (No Exposure in Responses)
# =============================================================================
def test_11_api_keys_never_exposed(test_app, client, setup_users):
    secret_key = "AIzaSy_SUPER_SECRET_KEY_12345"

    with patch.dict("os.environ", {"GEMINI_API_KEY": secret_key}):
        client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)

        payload = {
            "project_title": "Security Test System",
            "project_description": "Testing credential leakage prevention"
        }
        res = client.post("/api/project-analyzer/analyze", data=json.dumps(payload), content_type="application/json")
        response_text = res.data.decode("utf-8")

        # The API key must never appear anywhere in the HTTP response body
        assert secret_key not in response_text


# =============================================================================
# TEST 12: Friendly Error Handling When External APIs Fail
# =============================================================================
def test_12_friendly_error_handling_on_failure(test_app, client, setup_users):
    client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)

    # If the service raises an unexpected fatal error during processing,
    # the endpoint should catch it and return a graceful 500 JSON without exposing internal traceback
    with patch("app.routes.api.get_uniqueness_analyzer_service") as mock_get_svc:
        mock_svc = MagicMock()
        mock_svc.execute_analysis_pipeline.side_effect = Exception("Network connection refused")
        mock_get_svc.return_value = mock_svc

        payload = {"project_title": "Network Error Test"}
        res = client.post("/api/project-analyzer/analyze", data=json.dumps(payload), content_type="application/json")

        assert res.status_code == 500
        data = res.get_json()
        assert data["status"] == "error"
        assert "Unable to complete project analysis at this time" in data["message"]
        assert "Traceback" not in res.data.decode("utf-8")
