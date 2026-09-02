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
