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
    technologies_known = db.Column(db.String(255), nullable=True, default="")
    technology_difficulty = db.Column(db.String(20), nullable=False, default="Medium")  # Easy, Medium, Hard
    
    ai_tools_json = db.Column(db.Text, nullable=True)  # JSON list of recommended AI tools & prompts
    architecture_recommendation = db.Column(db.Text, nullable=True)  # Recommended system architecture
    requirements_json = db.Column(db.Text, nullable=True)  # Stage 1 structured requirements JSON
    confidence_score = db.Column(db.Float, default=100.0)  # AI project understanding confidence (0-100)
    clarification_questions_json = db.Column(db.Text, nullable=True)  # List of clarification questions if confidence < 80
    clarification_answers_json = db.Column(db.Text, nullable=True)  # Student answers to clarification questions
    plan_approved = db.Column(db.Boolean, default=False)  # Whether the roadmap plan was reviewed and approved
    
    project_category = db.Column(db.String(50), nullable=False, default="software")  # "software", "hardware", "hybrid"
    hardware_feasibility_status = db.Column(db.String(50), nullable=False, default="NOT_APPLICABLE")  # NOT_APPLICABLE, PENDING_REVIEW, APPROVED, MODIFICATION_REQUIRED
    
    initial_task_count = db.Column(db.Integer, default=0)
    health_score = db.Column(db.Float, default=75.0)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tasks = db.relationship("Task", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="Task.phase_number.asc(), Task.id.asc()")
    progress_records = db.relationship("ProjectProgress", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(ProjectProgress.created_at)")
    predictions = db.relationship("Prediction", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(Prediction.created_at)")
    checkins = db.relationship("ProjectCheckin", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(ProjectCheckin.created_at)")
    chat_messages = db.relationship("AIMentorMessage", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="AIMentorMessage.created_at.asc()")
    feedback_records = db.relationship("FacultyFeedback", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(FacultyFeedback.created_at)")
    alerts = db.relationship("EarlyWarningAlert", backref="project", lazy="dynamic", cascade="all, delete-orphan", order_by="desc(EarlyWarningAlert.created_at)")
    resources = db.relationship("ProjectResource", backref="project", lazy="dynamic", cascade="all, delete-orphan")
    ai_recommendations = db.relationship("AIRecommendation", backref="project", lazy="dynamic", cascade="all, delete-orphan")
    hardware_analysis = db.relationship("HardwareAnalysis", backref="project", uselist=False, cascade="all, delete-orphan")

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

    def get_ai_tools(self):
        """Returns parsed list of recommended AI tools with stage and copyable prompts."""
        if self.ai_tools_json:
            try:
                return json.loads(self.ai_tools_json)
            except Exception:
                return []
        return []

    def get_requirements(self):
        """Returns parsed Stage 1 structured requirements dictionary."""
        if self.requirements_json:
            try:
                return json.loads(self.requirements_json)
            except Exception:
                return {}
        return {}

    def get_clarification_questions(self):
        """Returns parsed list of clarification questions."""
        if self.clarification_questions_json:
            try:
                return json.loads(self.clarification_questions_json)
            except Exception:
                return []
        return []

    def get_clarification_answers(self):
        """Returns parsed dictionary of student clarification answers."""
        if self.clarification_answers_json:
            try:
                return json.loads(self.clarification_answers_json)
            except Exception:
                return {}
        return {}

    def get_timeline_pacing(self):
        """
        Compares task completion percentage against timeline elapsed percentage.
        Detects schedule lag, timeline risk, and generates alert messages.
        """
        today = date.today()
        total_days = max(1, (self.deadline - self.start_date).days)
        elapsed_days = max(0, (today - self.start_date).days)
        time_percentage = min(100.0, round((elapsed_days / total_days) * 100.0, 1))
        
        progress_percentage = self.calculated_progress_pct
        days_remaining = max(0, (self.deadline - today).days)
        
        # Risk condition: timeline elapsed running significantly ahead of tasks done
        gap = round(time_percentage - progress_percentage, 1)
        is_risk_detected = (gap >= 15.0 and time_percentage >= 20.0) or (days_remaining <= 14 and progress_percentage < 60.0)
        
        risk_message = ""
        if is_risk_detected:
            p_display = int(progress_percentage) if progress_percentage == int(progress_percentage) else progress_percentage
            t_display = int(time_percentage) if time_percentage == int(time_percentage) else time_percentage
            risk_message = f"⚠️ Project Risk Detected: You have completed only {p_display}% of the development tasks, but {t_display}% of your project timeline has passed."

        return {
            "total_days": total_days,
            "elapsed_days": elapsed_days,
            "days_remaining": days_remaining,
            "time_percentage": time_percentage,
            "progress_percentage": progress_percentage,
            "gap": gap,
            "is_risk_detected": is_risk_detected,
            "risk_message": risk_message
        }

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
    
    # 6 Phases: Phase 1 — Research & Planning, Phase 2 — UI/UX Design, etc.
    phase = db.Column(db.String(100), nullable=False, default="Phase 1 — Research & Planning")
    phase_number = db.Column(db.Integer, nullable=False, default=1)
    estimated_hours = db.Column(db.Float, nullable=False, default=4.0)
    can_parallel = db.Column(db.Boolean, default=False)
    
    status = db.Column(db.String(30), nullable=False, default="Not Started") # Not Started, In Progress, Completed, Blocked, Optional
    is_core = db.Column(db.Boolean, default=True)
    is_optional = db.Column(db.Boolean, default=False)
    
    source = db.Column(db.String(30), default="AI_GENERATED")              # AI_GENERATED, STUDENT_ADDED, AI_SUGGESTED, FACULTY_ADDED
    reason = db.Column(db.Text, nullable=True)                              # Why AI suggested this task
    requirement_source = db.Column(db.String(255), nullable=True)          # Specific project requirement this task satisfies
    dependencies = db.Column(db.Text, nullable=True)                        # JSON list of task dependency titles
    blocker_reason = db.Column(db.Text, nullable=True)                     # Student note if marked Blocked
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    resources = db.relationship("ProjectResource", backref="task", lazy="dynamic")
    ai_recommendations = db.relationship("AIRecommendation", backref="task", lazy="dynamic")

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


class ProjectResource(db.Model):
    """External API, Dataset, or Development Tool required for project and task execution."""
    __tablename__ = "project_resources"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)

    resource_name = db.Column(db.String(200), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)  # "api", "dataset", "ai_tool", "documentation", "tool"
    purpose = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    why_needed = db.Column(db.Text, nullable=True)

    official_url = db.Column(db.String(500), nullable=True)
    documentation_url = db.Column(db.String(500), nullable=True)
    api_key_url = db.Column(db.String(500), nullable=True)
    download_url = db.Column(db.String(500), nullable=True)

    authentication_required = db.Column(db.Boolean, default=False)
    pricing_information = db.Column(db.String(100), default="Free")
    verification_status = db.Column(db.String(50), default="Verified")  # Verified, Official Source, Requires API Key, Free Tier Available, etc.

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "task_title": self.task.title if self.task else None,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "purpose": self.purpose,
            "description": self.description,
            "why_needed": self.why_needed or self.description,
            "official_url": self.official_url,
            "documentation_url": self.documentation_url,
            "api_key_url": self.api_key_url,
            "download_url": self.download_url,
            "authentication_required": self.authentication_required,
            "pricing_information": self.pricing_information,
            "verification_status": self.verification_status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<ProjectResource {self.resource_name} [{self.resource_type}] (Project: {self.project_id})>"


class AIRecommendation(db.Model):
    """Contextual AI Tool recommendation with project-specific tailored prompts."""
    __tablename__ = "ai_tool_recommendations"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)

    tool_name = db.Column(db.String(100), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)  # Research, Coding, Debugging, UI/UX, Database, Documentation, Testing
    reason = db.Column(db.Text, nullable=False)
    official_url = db.Column(db.String(500), nullable=True)
    documentation_url = db.Column(db.String(500), nullable=True)
    generated_prompt = db.Column(db.Text, nullable=False)
    verification_status = db.Column(db.String(50), default="Verified")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "task_title": self.task.title if self.task else None,
            "tool_name": self.tool_name,
            "purpose": self.purpose,
            "reason": self.reason,
            "official_url": self.official_url,
            "documentation_url": self.documentation_url,
            "generated_prompt": self.generated_prompt,
            "verification_status": self.verification_status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<AIRecommendation {self.tool_name} [{self.purpose}] (Project: {self.project_id})>"


class HardwareAnalysis(db.Model):
    """
    BuildCheck AI Hardware Feasibility, Bill of Materials, Electrical Calculations,
    and Budget Analysis record for Hardware and Hybrid projects.
    """
    __tablename__ = "hardware_analyses"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    project_category = db.Column(db.String(50), default="hardware")  # "hardware", "hybrid"
    overall_score = db.Column(db.Float, default=80.0)  # 0 to 100
    verdict = db.Column(db.String(50), default="BUILDABLE")  # BUILDABLE, BUILDABLE_WITH_MODIFICATIONS, NOT_RECOMMENDED
    verdict_badge = db.Column(db.String(50), default="🟢 BUILDABLE")
    verdict_reason = db.Column(db.Text, nullable=True)
    
    # Sub-scores (0 to 100)
    technical_score = db.Column(db.Float, default=85.0)
    availability_score = db.Column(db.Float, default=85.0)
    budget_score = db.Column(db.Float, default=80.0)
    power_score = db.Column(db.Float, default=80.0)
    compatibility_score = db.Column(db.Float, default=85.0)
    complexity_score = db.Column(db.Float, default=75.0)
    time_score = db.Column(db.Float, default=85.0)
    
    # System Architecture Components (JSON)
    inputs_json = db.Column(db.Text, nullable=True)         # Sensors, buttons, inputs
    processing_json = db.Column(db.Text, nullable=True)     # Controller, microprocessors
    outputs_json = db.Column(db.Text, nullable=True)        # Motors, displays, relays, buzzers
    communication_json = db.Column(db.Text, nullable=True)  # Wi-Fi, Bluetooth, LoRa, etc.
    power_json = db.Column(db.Text, nullable=True)          # Voltage rails, current, Watts, battery recommendations
    
    # Bill of Materials & Calculations (JSON)
    bom_json = db.Column(db.Text, nullable=True)
    compatibility_issues_json = db.Column(db.Text, nullable=True)
    gpio_analysis_json = db.Column(db.Text, nullable=True)
    
    # Budget Parameters & Breakdown
    student_budget = db.Column(db.Float, default=2000.0)
    estimated_total_cost = db.Column(db.Float, default=1650.0)
    essential_cost = db.Column(db.Float, default=1400.0)
    optional_cost = db.Column(db.Float, default=250.0)
    remaining_budget = db.Column(db.Float, default=350.0)
    budget_status = db.Column(db.String(50), default="WITHIN_BUDGET")  # WITHIN_BUDGET, OVER_BUDGET
    available_components_json = db.Column(db.Text, nullable=True)
    preferred_controller = db.Column(db.String(100), nullable=True, default="ESP32")
    preferred_marketplace = db.Column(db.String(100), nullable=True, default="Robu.in")
    
    # Modifications & Real Online Products
    modifications_json = db.Column(db.Text, nullable=True)
    products_cache_json = db.Column(db.Text, nullable=True)
    
    # Enhanced Hardware Analysis & Working System Fields
    wiring_table_json = db.Column(db.Text, nullable=True)          # Detailed pin-by-pin connections table
    software_reqs_json = db.Column(db.Text, nullable=True)         # Languages, IDEs, required libraries, APIs
    testing_verification_json = db.Column(db.Text, nullable=True)  # Will this work rationale, failure modes, test steps
    troubleshooting_json = db.Column(db.Text, nullable=True)       # Contextual hardware fault troubleshooting steps
    budget_tiers_json = db.Column(db.Text, nullable=True)          # Minimum budget vs Recommended budget breakdown
    min_budget_cost = db.Column(db.Float, default=1200.0)          # Cost of minimal/clone build
    recommended_budget_cost = db.Column(db.Float, default=1850.0)  # Cost of robust recommended build
    processing_logic_text = db.Column(db.Text, nullable=True)      # Controller firmware processing logic
    expected_output_text = db.Column(db.Text, nullable=True)       # Expected output behaviors and readings
    
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def get_inputs(self):
        if self.inputs_json:
            try:
                return json.loads(self.inputs_json)
            except Exception:
                return []
        return []

    def get_processing(self):
        if self.processing_json:
            try:
                return json.loads(self.processing_json)
            except Exception:
                return []
        return []

    def get_outputs(self):
        if self.outputs_json:
            try:
                return json.loads(self.outputs_json)
            except Exception:
                return []
        return []

    def get_communication(self):
        if self.communication_json:
            try:
                return json.loads(self.communication_json)
            except Exception:
                return []
        return []

    def get_power(self):
        if self.power_json:
            try:
                return json.loads(self.power_json)
            except Exception:
                return {}
        return {}

    def get_bom(self):
        if self.bom_json:
            try:
                return json.loads(self.bom_json)
            except Exception:
                return []
        return []

    def get_compatibility_issues(self):
        if self.compatibility_issues_json:
            try:
                return json.loads(self.compatibility_issues_json)
            except Exception:
                return []
        return []

    def get_gpio_analysis(self):
        if self.gpio_analysis_json:
            try:
                return json.loads(self.gpio_analysis_json)
            except Exception:
                return {}
        return {}

    def get_available_components(self):
        if self.available_components_json:
            try:
                return json.loads(self.available_components_json)
            except Exception:
                return []
        return []

    def get_modifications(self):
        if self.modifications_json:
            try:
                return json.loads(self.modifications_json)
            except Exception:
                return []
        return []

    def get_products(self):
        if self.products_cache_json:
            try:
                return json.loads(self.products_cache_json)
            except Exception:
                return {}
        return {}

    def get_wiring_table(self):
        if self.wiring_table_json:
            try:
                return json.loads(self.wiring_table_json)
            except Exception:
                return []
        return []

    def get_software_reqs(self):
        if self.software_reqs_json:
            try:
                return json.loads(self.software_reqs_json)
            except Exception:
                return {}
        return {}

    def get_testing_verification(self):
        if self.testing_verification_json:
            try:
                return json.loads(self.testing_verification_json)
            except Exception:
                return {}
        return {}

    def get_troubleshooting(self):
        if self.troubleshooting_json:
            try:
                return json.loads(self.troubleshooting_json)
            except Exception:
                return []
        return []

    def get_budget_tiers(self):
        if self.budget_tiers_json:
            try:
                return json.loads(self.budget_tiers_json)
            except Exception:
                return {}
        return {}

    def get_feasibility_checks(self):
        tv = self.get_testing_verification()
        if isinstance(tv, dict) and "feasibility_checks" in tv:
            return tv["feasibility_checks"]
        return []

    def get_feasibility_verification(self):
        tv = self.get_testing_verification()
        if isinstance(tv, dict) and "feasibility_verification" in tv:
            return tv["feasibility_verification"]
        return {
            "feasibility": "FEASIBLE" if self.overall_score >= 80 else ("FEASIBLE_WITH_CHANGES" if self.overall_score >= 55 else "NOT_FEASIBLE"),
            "confidence": "HIGH" if self.overall_score >= 80 else "MEDIUM",
            "verdict_reasoning": self.verdict_reason or "Design verified for engineering feasibility.",
            "issues": [iss.get("issue") if isinstance(iss, dict) else str(iss) for iss in self.get_compatibility_issues()],
            "missing_components": [],
            "power_issues": [],
            "compatibility_issues": [iss.get("issue") if isinstance(iss, dict) else str(iss) for iss in self.get_compatibility_issues()],
            "required_changes": [m.get("action") if isinstance(m, dict) else str(m) for m in self.get_modifications()]
        }

    def get_primary_components(self):
        bom = self.get_bom()
        primary = []
        for item in bom:
            cat = str(item.get("category", "")).lower()
            name = str(item.get("name", item.get("component_name", ""))).lower()
            if cat in ["supporting", "prototyping", "power"] or any(k in name for k in ["resistor", "capacitor", "diode", "jumper", "breadboard", "cable", "adapter", "buck", "regulator", "clip"]):
                continue
            primary.append(item)
        return primary if primary else bom

    def get_supporting_components(self):
        bom = self.get_bom()
        supporting = []
        for item in bom:
            cat = str(item.get("category", "")).lower()
            name = str(item.get("name", item.get("component_name", ""))).lower()
            if cat in ["supporting", "prototyping", "power"] or any(k in name for k in ["resistor", "capacitor", "diode", "jumper", "wire", "breadboard", "cable", "adapter", "buck", "regulator", "holder", "clip", "heatsink"]):
                supporting.append(item)
        return supporting

    def get_power_architecture(self):
        p = self.get_power()
        if isinstance(p, dict) and "power_architecture" in p:
            return p["power_architecture"]
        if isinstance(p, dict) and "power_supply" in p:
            return p
        # Formulate structured power dict from electrical calculations
        return {
            "power_supply": p.get("recommended_power_source", "5V 2A Regulated USB Power Supply"),
            "input_voltage": p.get("recommended_psu_voltage", "5.0V DC"),
            "total_estimated_current": f"{p.get('total_current_safe_ma', 500)} mA continuous",
            "peak_current": f"{int(p.get('total_current_safe_ma', 500) * 1.5)} mA maximum burst demand",
            "regulators_required": p.get("regulators_required", []),
            "power_warnings": [iss.get("description", str(iss)) for iss in self.get_compatibility_issues() if "power" in str(iss).lower() or "current" in str(iss).lower() or "voltage" in str(iss).lower()]
        }

    def get_project_understanding(self):
        tv = self.get_testing_verification()
        if isinstance(tv, dict) and "project_understanding" in tv:
            return tv["project_understanding"]
        return {
            "summary": self.project.description if self.project else "",
            "primary_objective": self.project.objective if self.project and hasattr(self.project, "objective") else "",
            "operating_environment": "Lab Benchtop Prototyping",
            "detected_sensors": [item.get("name") for item in self.get_inputs()],
            "detected_actuators": [item.get("name") for item in self.get_outputs()],
            "detected_controller": self.preferred_controller or "ESP32",
            "communication_protocol": "Wi-Fi / Serial"
        }

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_category": self.project_category,
            "overall_score": self.overall_score,
            "verdict": self.verdict,
            "verdict_badge": self.verdict_badge,
            "verdict_reason": self.verdict_reason,
            "scores": {
                "technical": self.technical_score,
                "availability": self.availability_score,
                "budget": self.budget_score,
                "power": self.power_score,
                "compatibility": self.compatibility_score,
                "complexity": self.complexity_score,
                "time": self.time_score
            },
            "inputs": self.get_inputs(),
            "processing": self.get_processing(),
            "outputs": self.get_outputs(),
            "communication": self.get_communication(),
            "power": self.get_power(),
            "bom": self.get_bom(),
            "compatibility_issues": self.get_compatibility_issues(),
            "gpio_analysis": self.get_gpio_analysis(),
            "wiring_table": self.get_wiring_table(),
            "software_reqs": self.get_software_reqs(),
            "testing_verification": self.get_testing_verification(),
            "feasibility_checks": self.get_feasibility_checks(),
            "troubleshooting": self.get_troubleshooting(),
            "budget_tiers": self.get_budget_tiers(),
            "min_budget_cost": self.min_budget_cost,
            "recommended_budget_cost": self.recommended_budget_cost,
            "processing_logic_text": self.processing_logic_text or "",
            "expected_output_text": self.expected_output_text or "",
            "budget": {
                "student_budget": self.student_budget,
                "estimated_total_cost": self.estimated_total_cost,
                "essential_cost": self.essential_cost,
                "optional_cost": self.optional_cost,
                "remaining_budget": self.remaining_budget,
                "budget_status": self.budget_status,
                "available_components": self.get_available_components(),
                "preferred_controller": self.preferred_controller,
                "preferred_marketplace": self.preferred_marketplace,
                "min_budget_cost": self.min_budget_cost,
                "recommended_budget_cost": self.recommended_budget_cost
            },
            "modifications": self.get_modifications(),
            "products": self.get_products(),
            "is_approved": self.is_approved,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<HardwareAnalysis Project {self.project_id}: Score {self.overall_score} [{self.verdict}]>"


def upgrade_database_schema(app):
    """Safely adds newly required columns and tables to existing SQLite database tables."""
    from sqlalchemy import inspect, text
    with app.app_context():
        try:
            # Ensure newly defined tables exist
            db.create_all()

            inspector = inspect(db.engine)
            
            # Check projects table
            if "projects" in inspector.get_table_names():
                proj_cols = [c["name"] for c in inspector.get_columns("projects")]
                with db.engine.connect() as conn:
                    if "technologies_known" not in proj_cols:
                        conn.execute(text("ALTER TABLE projects ADD COLUMN technologies_known VARCHAR(255) DEFAULT ''"))
                    if "ai_tools_json" not in proj_cols:
                        conn.execute(text("ALTER TABLE projects ADD COLUMN ai_tools_json TEXT"))
                    if "architecture_recommendation" not in proj_cols:
                        conn.execute(text("ALTER TABLE projects ADD COLUMN architecture_recommendation TEXT"))
                    if "project_category" not in proj_cols:
                        conn.execute(text("ALTER TABLE projects ADD COLUMN project_category VARCHAR(50) DEFAULT 'software'"))
                    if "hardware_feasibility_status" not in proj_cols:
                        conn.execute(text("ALTER TABLE projects ADD COLUMN hardware_feasibility_status VARCHAR(50) DEFAULT 'NOT_APPLICABLE'"))
                    conn.commit()

            # Check tasks table
            if "tasks" in inspector.get_table_names():
                task_cols = [c["name"] for c in inspector.get_columns("tasks")]
                with db.engine.connect() as conn:
                    if "phase" not in task_cols:
                        conn.execute(text("ALTER TABLE tasks ADD COLUMN phase VARCHAR(100) DEFAULT 'Phase 1 — Research & Planning'"))
                    if "phase_number" not in task_cols:
                        conn.execute(text("ALTER TABLE tasks ADD COLUMN phase_number INTEGER DEFAULT 1"))
                    if "estimated_hours" not in task_cols:
                        conn.execute(text("ALTER TABLE tasks ADD COLUMN estimated_hours FLOAT DEFAULT 4.0"))
                    if "can_parallel" not in task_cols:
                        conn.execute(text("ALTER TABLE tasks ADD COLUMN can_parallel BOOLEAN DEFAULT 0"))
                    conn.commit()

            # Check hardware_analyses table
            if "hardware_analyses" in inspector.get_table_names():
                hw_cols = [c["name"] for c in inspector.get_columns("hardware_analyses")]
                with db.engine.connect() as conn:
                    if "wiring_table_json" not in hw_cols:
                        conn.execute(text("ALTER TABLE hardware_analyses ADD COLUMN wiring_table_json TEXT"))
                    if "software_reqs_json" not in hw_cols:
                        conn.execute(text("ALTER TABLE hardware_analyses ADD COLUMN software_reqs_json TEXT"))
                    if "testing_verification_json" not in hw_cols:
                        conn.execute(text("ALTER TABLE hardware_analyses ADD COLUMN testing_verification_json TEXT"))
                    if "troubleshooting_json" not in hw_cols:
                        conn.execute(text("ALTER TABLE hardware_analyses ADD COLUMN troubleshooting_json TEXT"))
                    if "budget_tiers_json" not in hw_cols:
                        conn.execute(text("ALTER TABLE hardware_analyses ADD COLUMN budget_tiers_json TEXT"))
                    if "min_budget_cost" not in hw_cols:
                        conn.execute(text("ALTER TABLE hardware_analyses ADD COLUMN min_budget_cost FLOAT DEFAULT 1200.0"))
                    if "recommended_budget_cost" not in hw_cols:
                        conn.execute(text("ALTER TABLE hardware_analyses ADD COLUMN recommended_budget_cost FLOAT DEFAULT 1850.0"))
                    if "processing_logic_text" not in hw_cols:
                        conn.execute(text("ALTER TABLE hardware_analyses ADD COLUMN processing_logic_text TEXT"))
                    if "expected_output_text" not in hw_cols:
                        conn.execute(text("ALTER TABLE hardware_analyses ADD COLUMN expected_output_text TEXT"))
                    conn.commit()
        except Exception as e:
            # If in-memory or already up to date, silently continue
            pass

