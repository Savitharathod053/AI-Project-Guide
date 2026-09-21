"""Student Project Isolation and Progress Management Tests."""
from datetime import date, timedelta
import pytest
from app import create_app
from app.models import db, User, Project, ProjectProgress


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


def test_project_creation_and_isolation(test_app, client):
    with test_app.app_context():
        # Create student 1
        s1 = User(name="Student One", email="s1@college.edu", role="student")
        s1.set_password("pass123")
        db.session.add(s1)

        # Create student 2
        s2 = User(name="Student Two", email="s2@college.edu", role="student")
        s2.set_password("pass123")
        db.session.add(s2)
        db.session.commit()

        # Create project for student 1
        p1 = Project(
            owner_id=s1.id,
            project_name="AI Image Classifier",
            description="Deep learning image classification system using CNNs.",
            domain="Machine Learning & AI",
            technology_difficulty="Medium",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=40)
        )
        db.session.add(p1)
        db.session.commit()
        p1_id = p1.id

    # Login as student 2
    client.post("/auth/login", data={"email": "s2@college.edu", "password": "pass123"}, follow_redirects=True)

    # Student 2 tries to access Student 1's project -> should receive 404/Forbidden
    res = client.get(f"/student/projects/{p1_id}")
    assert res.status_code == 404


def test_create_project_with_ai_and_phases(test_app, client):
    """Test full AI project creation workflow with 6 submission fields and 6 phases."""
    with test_app.app_context():
        student = User(name="Alice Student", email="alice@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

    # Login
    client.post("/auth/login", data={"email": "alice@college.edu", "password": "pass123"}, follow_redirects=True)

    # Submit project
    deadline_str = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
    post_data = {
        "project_name": "AI-Based Campus Event Management System",
        "description": "A web application for managing college events, registrations, approvals, and certificates.",
        "domain": "Web Development",
        "deadline": deadline_str,
        "team_size": "3",
        "technologies_known": "HTML, CSS, JavaScript, Python",
        "technology_difficulty": "Medium"
    }
    res = client.post("/student/projects/new", data=post_data, follow_redirects=True)
    assert res.status_code == 200
    assert b"Phase 1" in res.data or b"Review" in res.data or b"Tasks" in res.data

    with test_app.app_context():
        p = Project.query.filter_by(project_name="AI-Based Campus Event Management System").first()
        assert p is not None
        assert p.technologies_known == "HTML, CSS, JavaScript, Python"
        assert p.team_size == 3
        tasks_list = p.tasks.all()
        assert len(tasks_list) >= 6
        
        # Verify tasks have phase information and estimated hours
        phases_present = {t.phase for t in tasks_list if t.phase}
        assert len(phases_present) >= 3
        assert any("Research" in ph for ph in phases_present)

        # Verify AI tools & architecture recommendation were generated
        ai_tools = p.get_ai_tools()
        assert len(ai_tools) >= 1
        assert any("tool_name" in item or "stage" in item for item in ai_tools)


def test_timeline_pacing_risk_detector(test_app):
    """Verify that project risk detector triggers the exact warning message when schedule lags."""
    with test_app.app_context():
        student = User(name="Bob Student", email="bob@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        # Start 60 days ago, deadline in 40 days -> 60% time elapsed
        p = Project(
            owner_id=student.id,
            project_name="Pacing Test Project",
            description="Testing timeline risk detector.",
            domain="Web Development",
            start_date=date.today() - timedelta(days=60),
            deadline=date.today() + timedelta(days=40)
        )
        db.session.add(p)
        db.session.commit()

        # Add 10 tasks: 3 Completed (30%), 7 Not Started
        from app.models import Task
        for i in range(10):
            t = Task(
                project_id=p.id,
                title=f"Task {i+1}",
                category="Backend",
                phase="Phase 3 — Development",
                status="Completed" if i < 3 else "Not Started",
                estimated_hours=4.0
            )
            db.session.add(t)
        db.session.commit()

        pacing = p.get_timeline_pacing()
        assert pacing["time_percentage"] == 60
        assert pacing["progress_percentage"] == 30
        assert pacing["is_risk_detected"] is True
        assert "⚠️ Project Risk Detected: You have completed only 30% of the development tasks, but 60% of your project timeline has passed." in pacing["risk_message"]


def test_task_editing_and_status_transitions(test_app, client):
    """Test editing task fields, updating status to Blocked with note, and completing tasks."""
    with test_app.app_context():
        student = User(name="Carol Student", email="carol@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        p = Project(
            owner_id=student.id,
            project_name="Task Management Test",
            description="Testing task operations.",
            domain="Web Development",
            deadline=date.today() + timedelta(days=30)
        )
        db.session.add(p)
        db.session.commit()

        from app.models import Task
        t = Task(
            project_id=p.id,
            title="Old Task Title",
            description="Old description",
            category="Backend",
            phase="Phase 3 — Development",
            estimated_hours=4.0,
            priority="Medium",
            difficulty="Medium",
            status="Not Started"
        )
        db.session.add(t)
        db.session.commit()
        p_id = p.id
        t_id = t.id

    client.post("/auth/login", data={"email": "carol@college.edu", "password": "pass123"}, follow_redirects=True)

    # 1. Edit Task
    edit_data = {
        "title": "Implement JWT Auth Service",
        "description": "Create token auth route and refresh mechanism",
        "phase": "Phase 3 — Development",
        "category": "Backend",
        "priority": "Critical",
        "difficulty": "Hard",
        "estimated_hours": "6.5"
    }
    res = client.post(f"/student/projects/{p_id}/tasks/{t_id}/edit", data=edit_data, follow_redirects=True)
    assert res.status_code == 200

    with test_app.app_context():
        updated_t = db.session.get(Task, t_id)
        assert updated_t.title == "Implement JWT Auth Service"
        assert updated_t.priority == "Critical"
        assert updated_t.estimated_hours == 6.5

    # 2. Update Status to Blocked with note
    res_block = client.post(
        f"/student/projects/{p_id}/tasks/{t_id}/status",
        data={"status": "Blocked", "blocker_reason": "CORS error on authorization header"},
        follow_redirects=True
    )
    assert res_block.status_code == 200

    with test_app.app_context():
        blocked_t = db.session.get(Task, t_id)
        assert blocked_t.status == "Blocked"
        assert "CORS" in blocked_t.blocker_reason

    # 3. Regenerate tasks
    res_regen = client.post(
        f"/student/projects/{p_id}/tasks/regenerate",
        data={"instructions": "Focus on security testing and automated CI/CD"},
        follow_redirects=True
    )
    assert res_regen.status_code == 200

    with test_app.app_context():
        p_refreshed = db.session.get(Project, p_id)
        assert p_refreshed.tasks.count() > 0

