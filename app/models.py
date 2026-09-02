import json
from datetime import datetime, timezone, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User account model for Students and Faculty."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # "student", "faculty"
    department = db.Column(db.String(100), nullable=True, default="Computer Science & Engineering")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    projects = db.relationship("Project", backref="owner", lazy="dynamic", foreign_keys="Project.owner_id")
    feedback_given = db.relationship("FacultyFeedback", backref="faculty", lazy="dynamic", foreign_keys="FacultyFeedback.faculty_id")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_faculty(self) -> bool:
        return self.role == "faculty"

    @property
    def is_student(self) -> bool:
        return self.role == "student"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Project(db.Model):
    """Academic project entity managed by a student and mentored by AI."""
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    project_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True, default="")
    objective = db.Column(db.Text, nullable=True, default="")
    project_summary = db.Column(db.Text, nullable=True, default="")
    
    domain = db.Column(db.String(100), nullable=False, default="Web Development")
    project_type = db.Column(db.String(100), nullable=False, default="Capstone Project")
    team_size = db.Column(db.Integer, nullable=False, default=1)
    team_members = db.Column(db.Text, nullable=True)
    
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    deadline = db.Column(db.Date, nullable=False)
    
    technologies = db.Column(db.String(255), nullable=True, default="Python, JavaScript")
    technologies_count = db.Column(db.Integer, default=2)
    technology_difficulty = db.Column(db.String(20), nullable=False, default="Medium")  # Easy, Medium, Hard
    
    initial_task_count = db.Column(db.Integer, default=0)
    health_score = db.Column(db.Float, default=75.0)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tasks = db.relationship("Task", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="Task.created_at.asc()")
    progress_records = db.relationship("ProjectProgress", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(ProjectProgress.created_at)")
    predictions = db.relationship("Prediction", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(Prediction.created_at)")
    checkins = db.relationship("ProjectCheckin", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(ProjectCheckin.created_at)")
    chat_messages = db.relationship("AIMentorMessage", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="AIMentorMessage.created_at.asc()")
    feedback_records = db.relationship("FacultyFeedback", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(FacultyFeedback.created_at)")
    alerts = db.relationship("EarlyWarningAlert", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(EarlyWarningAlert.created_at)")

    @property
    def latest_progress(self):
        return self.progress_records.first()

    @property
    def latest_prediction(self):
        return self.predictions.first()

    @property
    def latest_checkin(self):
        return self.checkins.first()

    @property
    def completed_tasks_count(self):
        return self.tasks.filter_by(status="Completed").count()

    @property
    def in_progress_tasks_count(self):
        return self.tasks.filter_by(status="In Progress").count()

    @property
    def blocked_tasks_count(self):
        return self.tasks.filter_by(status="Blocked").count()

    @property
    def pending_tasks_count(self):
        return self.tasks.filter(Task.status.in_(["Not Started", "In Progress", "Blocked"])).count()

    @property
    def total_tasks_count(self):
        return self.tasks.count()

    @property
    def calculated_progress_pct(self):
        total = self.total_tasks_count
        if total == 0:
            return 0.0
        return round((self.completed_tasks_count / total) * 100.0, 1)

    def __repr__(self):
        return f"<Project {self.project_name} (ID: {self.id})>"


class Task(db.Model):
    """Actionable development task generated by AI or added by student/faculty."""
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False, default="Backend")  # Database, Frontend, Backend, ML, API, Testing, Docs, etc.
    priority = db.Column(db.String(20), nullable=False, default="High")     # Critical, High, Medium, Low, Optional
    difficulty = db.Column(db.String(20), default="Medium")                # Easy, Medium, Hard
    
    status = db.Column(db.String(30), nullable=False, default="Not Started") # Not Started, In Progress, Completed, Blocked, Optional
    is_core = db.Column(db.Boolean, default=True)
    is_optional = db.Column(db.Boolean, default=False)
    
    source = db.Column(db.String(30), default="AI_GENERATED")              # AI_GENERATED, STUDENT_ADDED, AI_SUGGESTED, FACULTY_ADDED
    reason = db.Column(db.Text, nullable=True)                              # Why AI suggested this task
    dependencies = db.Column(db.Text, nullable=True)                        # JSON list of task dependency titles
    blocker_reason = db.Column(db.Text, nullable=True)                     # Student note if marked Blocked
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def get_dependencies_list(self):
        if self.dependencies:
            try:
                return json.loads(self.dependencies)
            except Exception:
                return []
        return []

    def __repr__(self):
        return f"<Task {self.title} [{self.status}] (Project: {self.project_id})>"


class ProjectProgress(db.Model):
    """Periodic progress snapshot submitted by the student or synced with Task Board."""
    __tablename__ = "project_progress"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Task metrics
    total_tasks = db.Column(db.Integer, nullable=False, default=10)
    completed_tasks = db.Column(db.Integer, nullable=False, default=0)
    pending_tasks = db.Column(db.Integer, nullable=False, default=10)
    delayed_tasks = db.Column(db.Integer, nullable=False, default=0)
    blocked_tasks = db.Column(db.Integer, nullable=False, default=0)
    progress_percentage = db.Column(db.Float, nullable=False, default=0.0)
    
    # Development quality metrics
    core_features_completed = db.Column(db.Float, default=0.0)
    optional_features_completed = db.Column(db.Float, default=0.0)
    testing_percentage = db.Column(db.Float, nullable=False, default=0.0)
    documentation_percentage = db.Column(db.Float, nullable=False, default=0.0)
    presentation_percentage = db.Column(db.Float, nullable=False, default=0.0)
    bugs = db.Column(db.Integer, nullable=False, default=0)
    
    # Team & Evaluation
    collaboration_rating = db.Column(db.Float, default=4.0)  # 1.0 to 5.0
    evaluation_score = db.Column(db.Float, default=70.0)     # Previous score 0-100
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    prediction = db.relationship("Prediction", backref="progress", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProjectProgress Project {self.project_id} - {self.progress_percentage}%>"


class Prediction(db.Model):
    """Risk prediction result generated by the ML pipeline for a progress record."""
    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    progress_id = db.Column(db.Integer, db.ForeignKey("project_progress.id", ondelete="CASCADE"), nullable=True)
    
    success_probability = db.Column(db.Float, nullable=False)  # 0.0 to 100.0 %
    failure_probability = db.Column(db.Float, nullable=False)  # 0.0 to 100.0 %
    risk_level = db.Column(db.String(20), nullable=False)      # LOW, MODERATE, HIGH, CRITICAL
    model_version = db.Column(db.String(50), default="ML_Classifier_v1.0")
    
    # Stored JSON details for Explainable AI
    shap_values = db.Column(db.Text, nullable=True)             # JSON list of feature attributions
    risk_factors_list = db.Column(db.Text, nullable=True)       # JSON list of top identified risk drivers
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    recommendations = db.relationship("Recommendation", backref="prediction", lazy="dynamic", cascade="all, delete-orphan")

    def get_shap_list(self):
        if self.shap_values:
            try:
                return json.loads(self.shap_values)
            except Exception:
                return []
        return []

    def get_risk_factors(self):
        if self.risk_factors_list:
            try:
                return json.loads(self.risk_factors_list)
            except Exception:
                return []
        return []

    def __repr__(self):
        return f"<Prediction Project {self.project_id}: Risk {self.risk_level} ({self.failure_probability}%)>"


class Recommendation(db.Model):
    """Actionable guidance derived by the recommendation engine for a prediction."""
    __tablename__ = "recommendations"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    prediction_id = db.Column(db.Integer, db.ForeignKey("predictions.id", ondelete="CASCADE"), nullable=True)
    
    risk_factor = db.Column(db.String(255), nullable=False)
    recommendation = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default="High")  # Urgent, High, Medium, Info
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Recommendation {self.priority}: {self.risk_factor}>"


class ProjectCheckin(db.Model):
    """AI Smart Check-In snapshot and health assessment."""
    __tablename__ = "project_checkins"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    health_score = db.Column(db.Float, default=75.0)
    risk_level = db.Column(db.String(20), default="LOW")
    ai_summary = db.Column(db.Text, nullable=False)
    recommendations_json = db.Column(db.Text, nullable=True)
    
    task_completion_score = db.Column(db.Float, default=80.0)
    schedule_score = db.Column(db.Float, default=75.0)
    testing_score = db.Column(db.Float, default=60.0)
    doc_score = db.Column(db.Float, default=70.0)
    blocked_score = db.Column(db.Float, default=90.0)
    core_score = db.Column(db.Float, default=80.0)
    
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def get_recommendations(self):
        if self.recommendations_json:
            try:
                return json.loads(self.recommendations_json)
            except Exception:
                return []
        return []

    def __repr__(self):
        return f"<ProjectCheckin Project {self.project_id} (Health: {self.health_score})>"


class AIMentorMessage(db.Model):
    """Interactive conversation message between student and AI Project Mentor."""
    __tablename__ = "ai_mentor_messages"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    role = db.Column(db.String(20), nullable=False)  # "user" or "assistant"
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<AIMentorMessage {self.role} in Project {self.project_id}>"


class FacultyFeedback(db.Model):
    """Faculty evaluation score, notes, and direct feedback."""
    __tablename__ = "faculty_feedback"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    score = db.Column(db.Float, nullable=True)  # 0 to 100
    feedback = db.Column(db.Text, nullable=False)
    milestone_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<FacultyFeedback Project {self.project_id} by Faculty {self.faculty_id}>"


class EarlyWarningAlert(db.Model):
    """Automated alert triggered when a project's risk increases sharply."""
    __tablename__ = "early_warning_alerts"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    prediction_id = db.Column(db.Integer, db.ForeignKey("predictions.id", ondelete="CASCADE"), nullable=True)
    
    previous_risk = db.Column(db.Float, nullable=False)
    current_risk = db.Column(db.Float, nullable=False)
    risk_jump = db.Column(db.Float, nullable=False)
    message = db.Column(db.Text, nullable=False)
    possible_reasons = db.Column(db.Text, nullable=True)
    recommended_action = db.Column(db.Text, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<EarlyWarningAlert Project {self.project_id}: +{self.risk_jump}% risk>"
