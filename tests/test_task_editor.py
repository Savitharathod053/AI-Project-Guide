import pytest
from app import create_app
from app.models import db, User, Project, Task, ProjectProgress
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
def student_client(test_app, client):
    """Creates an authenticated student user and client."""
    with test_app.app_context():
        user = User(
            name="Task Tester",
            email="task_tester@college.edu",
            role="student",
            department="Computer Science"
        )
        user.set_password("pass123")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client.post("/auth/login", data={
        "email": "task_tester@college.edu",
        "password": "pass123"
    }, follow_redirects=True)

    return client, user_id, test_app


def test_task_editor_visibility_and_navigation(student_client):
    """Test that the Task Editor tab button, tab pane, and toolbar are rendered and accessible."""
    client, user_id, test_app = student_client

    with test_app.app_context():
        project = Project(
            owner_id=user_id,
            project_name="Autonomous Solar Rover",
            description="Robotics rover with solar tracking sensors.",
            objective="Build hardware and vision rover.",
            domain="Robotics & IoT",
            team_size=2,
            technologies="Python, OpenCV, Arduino",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=60),
            initial_task_count=2
        )
        db.session.add(project)
        db.session.commit()

        task1 = Task(
            project_id=project.id,
            title="Design Chassis & Solar Bracket",
            description="3D model the bracket.",
            category="Research",
            priority="High",
            difficulty="Medium",
            phase="Phase 1 — Research & Planning",
            phase_number=1,
            estimated_hours=6.0,
            status="Not Started"
        )
        task2 = Task(
            project_id=project.id,
            title="Microcontroller Pinout & Wiring",
            description="Wire sensor pins.",
            category="Backend",
            priority="Critical",
            difficulty="Hard",
            phase="Phase 3 — Development",
            phase_number=3,
            estimated_hours=8.0,
            status="In Progress"
        )
        db.session.add_all([task1, task2])
        db.session.commit()
        proj_id = project.id

    resp = client.get(f"/student/projects/{proj_id}")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # 1. Verify Task Editor tab button is present in the Sidebar
    assert 'id="tasks-tab"' in html
    assert 'data-bs-target="#tasks"' in html
    assert "Task Editor & Plan" in html

    # 2. Verify Task Editor button is in Top Action Bar
    assert "Task Editor" in html

    # 3. Verify Overview "Open Task Editor" button is present
    assert "Open Task Editor" in html

    # 4. Verify Task Editor tab pane is present
    assert 'id="tasks"' in html
    assert "Development Plan & Task Editor" in html
    assert "Design Chassis &amp; Solar Bracket" in html or "Design Chassis & Solar Bracket" in html
    assert "Microcontroller Pinout &amp; Wiring" in html or "Microcontroller Pinout & Wiring" in html

    # 5. Verify Edit Task button contains data-* attributes
    assert "btn-edit-task" in html
    assert 'data-task-id="' in html
    assert "Design Chassis" in html
    assert 'data-status="Not Started"' in html

    # 6. Verify Modals are present
    assert 'id="editTaskModal"' in html
    assert 'id="edit_status"' in html
    assert 'id="addTaskModal"' in html


def test_edit_task_lifecycle_and_persistence(student_client):
    """Test editing task fields (title, description, status, priority, hours) and database persistence."""
    client, user_id, test_app = student_client

    with test_app.app_context():
        project = Project(
            owner_id=user_id,
            project_name="AI Image Classifier",
            description="Test project",
            objective="Test",
            domain="Computer Vision",
            team_size=1,
            technologies="Python",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=30),
            initial_task_count=1
        )
        db.session.add(project)
        db.session.commit()

        task = Task(
            project_id=project.id,
            title="Initial Setup Task",
            description="Old description",
            category="Backend",
            priority="Medium",
            difficulty="Medium",
            phase="Phase 1 — Research & Planning",
            phase_number=1,
            estimated_hours=4.0,
            status="Not Started"
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id
        proj_id = project.id

    # Submit edit request
    edit_resp = client.post(f"/student/projects/{proj_id}/tasks/{task_id}/edit", data={
        "title": "Design Chassis & Solar Bracket v2 (Updated)",
        "description": "Refined 3D model with aluminum reinforcement brackets.",
        "status": "In Progress",
        "phase": "Phase 1 — Research & Planning",
        "category": "Research",
        "priority": "Critical",
        "difficulty": "Hard",
        "estimated_hours": "12.5"
    }, follow_redirects=True)

    assert edit_resp.status_code == 200

    # Verify database persistence
    with test_app.app_context():
        updated_task = db.session.get(Task, task_id)
        assert updated_task.title == "Design Chassis & Solar Bracket v2 (Updated)"
        assert updated_task.description == "Refined 3D model with aluminum reinforcement brackets."
        assert updated_task.status == "In Progress"
        assert updated_task.priority == "Critical"
        assert updated_task.difficulty == "Hard"
        assert updated_task.estimated_hours == 12.5

    # Reload page and confirm updated data is rendered in the Task Editor
    page_resp = client.get(f"/student/projects/{proj_id}")
    page_html = page_resp.data.decode("utf-8")
    assert "Design Chassis &amp; Solar Bracket v2 (Updated)" in page_html or "Design Chassis & Solar Bracket v2 (Updated)" in page_html
    assert "Refined 3D model with aluminum reinforcement brackets." in page_html
    assert "12.5 hrs" in page_html


def test_update_task_status_direct(student_client):
    """Test 1-click status toggle/update route."""
    client, user_id, test_app = student_client

    with test_app.app_context():
        project = Project(
            owner_id=user_id,
            project_name="Status Test Project",
            description="Test project",
            objective="Test",
            domain="Computer Vision",
            team_size=1,
            technologies="Python",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=30),
            initial_task_count=1
        )
        db.session.add(project)
        db.session.commit()

        task = Task(
            project_id=project.id,
            title="Status Check Task",
            description="Testing status toggle",
            category="Testing",
            priority="High",
            difficulty="Medium",
            phase="Phase 5 — Testing",
            phase_number=5,
            estimated_hours=3.0,
            status="Not Started"
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id
        proj_id = project.id

    resp = client.post(f"/student/projects/{proj_id}/tasks/{task_id}/status", data={
        "status": "Completed"
    }, follow_redirects=True)

    assert resp.status_code == 200
    with test_app.app_context():
        updated = db.session.get(Task, task_id)
        assert updated.status == "Completed"


def test_delete_task_direct(student_client):
    """Test deleting task from Task Editor."""
    client, user_id, test_app = student_client

    with test_app.app_context():
        project = Project(
            owner_id=user_id,
            project_name="Delete Test Project",
            description="Test project",
            objective="Test",
            domain="Computer Vision",
            team_size=1,
            technologies="Python",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=30),
            initial_task_count=1
        )
        db.session.add(project)
        db.session.commit()

        task = Task(
            project_id=project.id,
            title="Task To Delete",
            description="Will be removed",
            category="Documentation",
            priority="Low",
            difficulty="Easy",
            phase="Phase 6 — Documentation & Deployment",
            phase_number=6,
            estimated_hours=2.0,
            status="Not Started"
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id
        proj_id = project.id

    resp = client.post(f"/student/projects/{proj_id}/tasks/{task_id}/delete", follow_redirects=True)
    assert resp.status_code == 200

    with test_app.app_context():
        assert db.session.get(Task, task_id) is None
