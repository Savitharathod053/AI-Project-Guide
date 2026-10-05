"""
PROJEXA FLASK APPLICATION FACTORY
=================================
Initializes Flask extensions, registers Student, Faculty, Auth, Main, and API blueprints,
and configures error handlers and security settings.
"""

import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from app.models import db, User
from config import config_dict

migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name: str = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_dict.get(config_name, config_dict["default"]))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import upgrade_database_schema
    upgrade_database_schema(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register Blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.faculty import faculty_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(faculty_bp, url_prefix="/faculty")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Exempt API blueprint from CSRF for programmatic / AJAX access if headers are used
    csrf.exempt(api_bp)

    # Register Error Handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("errors/500.html"), 500

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from app.models import Project
        recent_sidebar_projects = []
        if current_user.is_authenticated and hasattr(current_user, 'is_student') and current_user.is_student:
            try:
                recent_sidebar_projects = Project.query.filter_by(owner_id=current_user.id).order_by(Project.updated_at.desc()).limit(6).all()
            except Exception:
                recent_sidebar_projects = []
        return {
            "app_name": "Projexa",
            "current_year": 2026,
            "disclaimer_text": "Projexa provides statistical risk estimates based on historical project patterns. It does not guarantee evaluation outcomes.",
            "recent_sidebar_projects": recent_sidebar_projects
        }

    return app
