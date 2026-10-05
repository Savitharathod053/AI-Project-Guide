import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "projexa-dev-secret-key-998822")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ML & Data paths
    MODEL_DIR = BASE_DIR / "models"
    DATA_DIR = BASE_DIR / "data"
    
    # Model Artifacts
    TRAINED_MODEL_PATH = MODEL_DIR / "trained_model.pkl"
    PIPELINE_PATH = MODEL_DIR / "pipeline.pkl"
    FEATURE_CONFIG_PATH = MODEL_DIR / "feature_config.json"
    MODEL_METADATA_PATH = MODEL_DIR / "model_metadata.json"
    
    # Risk Thresholds
    RISK_THRESHOLDS = {
        "LOW": (0.0, 0.20),
        "MODERATE": (0.21, 0.40),
        "HIGH": (0.41, 0.60),
        "CRITICAL": (0.61, 1.00)
    }


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'projexa.db'}")


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


config_dict = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}
