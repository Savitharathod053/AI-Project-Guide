"""Authentication, Password Hashing & Role Authorization Tests."""
import pytest
from app import create_app
from app.models import db, User


@pytest.fixture
def client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.drop_all()


def test_user_registration(client):
    res = client.post("/auth/register", data={
        "name": "Jane Doe",
        "email": "jane@college.edu",
        "password": "securepassword123",
        "confirm_password": "securepassword123",
        "role": "student",
        "department": "Computer Science"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Jane Doe" in res.data


def test_password_hashing():
    u = User(name="Test User", email="test@college.edu", role="student")
    u.set_password("mypassword")
    assert u.password_hash != "mypassword"
    assert u.check_password("mypassword") is True
    assert u.check_password("wrongpassword") is False


def test_login_flow(client):
    # Register
    client.post("/auth/register", data={
        "name": "Prof Smith",
        "email": "prof@college.edu",
        "password": "password123",
        "confirm_password": "password123",
        "role": "faculty",
        "department": "Engineering"
    }, follow_redirects=True)

    # Logout
    client.get("/auth/logout", follow_redirects=True)

    # Login
    res = client.post("/auth/login", data={
        "email": "prof@college.edu",
        "password": "password123"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Prof Smith" in res.data
