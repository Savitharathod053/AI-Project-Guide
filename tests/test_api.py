"""REST API Endpoints & What-If Simulation Tests."""
from datetime import date, timedelta
import json
import pytest
from app import create_app
from app.models import db, User, Project, ProjectProgress, Prediction


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


def test_api_what_if_simulation(test_app, client):
    with test_app.app_context():
        u = User(name="Student Dev", email="studentdev@college.edu", role="student")
        u.set_password("pass123")
        db.session.add(u)
        db.session.commit()

        p = Project(
            owner_id=u.id,
            project_name="AI Robot Vision",
            description="AI robot vision obstacle detection and mapping.",
            domain="Machine Learning & AI",
            technology_difficulty="Hard",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=30)
        )
        db.session.add(p)
        db.session.commit()

        prog = ProjectProgress(
            project_id=p.id,
            total_tasks=20,
            completed_tasks=5,
            pending_tasks=15,
            delayed_tasks=4,
            progress_percentage=25.0,
            testing_percentage=10.0,
            documentation_percentage=10.0,
            bugs=4
        )
        db.session.add(prog)
        db.session.commit()

        pred = Prediction(
            project_id=p.id,
            progress_id=prog.id,
            success_probability=25.0,
            failure_probability=75.0,
            risk_level="CRITICAL"
        )
        db.session.add(pred)
        db.session.commit()
        project_id = p.id

    # Login
    client.post("/auth/login", data={"email": "studentdev@college.edu", "password": "pass123"}, follow_redirects=True)

    # Test What-If API call
    sim_payload = {
        "total_tasks": 20,
        "completed_tasks": 16, # +11 tasks
        "delayed_tasks": 0,    # 0 delayed
        "testing_percentage": 80.0, # 80% testing
        "documentation_percentage": 70.0,
        "bugs": 0,
        "days_remaining": 25
    }

    res = client.post(
        f"/api/projects/{project_id}/what-if",
        data=json.dumps(sim_payload),
        content_type="application/json"
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "simulated_failure_probability" in data
    assert "simulated_success_probability" in data
    assert "risk_improvement" in data
    # High testing and completed tasks should lower failure risk
    assert data["simulated_failure_probability"] < 75.0
    assert data["risk_improvement"] > 0
