"""
SMART RESOURCE FINDER & VERIFICATION SERVICE
===========================================
Analyzes student projects using Gemini AI to identify required APIs, Datasets,
and AI Tools, matches them against a verified official directory, validates
official links and documentation, and generates contextual prompts for tasks.
"""

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models import AIRecommendation, Project, ProjectResource, Task, db

logger = logging.getLogger(__name__)

# ==============================================================================
# OFFICIAL VERIFIED RESOURCE KNOWLEDGEBASE (Official sources, docs, downloads)
# ==============================================================================
OFFICIAL_RESOURCES_CATALOG: Dict[str, Dict[str, Any]] = {
    # ------------------ WEATHER & CLIMATE APIS ------------------
    "open_meteo": {
        "name": "Open-Meteo Weather API",
        "type": "api",
        "category": "Weather",
        "purpose": "Free real-time & historical weather forecast data with hourly granularity",
        "official_url": "https://open-meteo.com/",
        "documentation_url": "https://open-meteo.com/en/docs",
        "api_key_url": None,  # No API key required for non-commercial use!
        "download_url": None,
        "authentication_required": False,
        "pricing_information": "Free (No Key Required)",
        "verification_status": "Verified",
        "keywords": ["weather", "forecast", "temperature", "climate", "rainfall", "humidity", "wind", "precipitation"]
    },
    "openweathermap": {
        "name": "OpenWeatherMap API",
        "type": "api",
        "category": "Weather",
        "purpose": "Current weather, 5-day forecasts, and global weather maps",
        "official_url": "https://openweathermap.org/",
        "documentation_url": "https://openweathermap.org/api",
        "api_key_url": "https://home.openweathermap.org/users/sign_up",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available (1,000 calls/day)",
        "verification_status": "Verified",
        "keywords": ["weather", "forecast", "meteorology", "atmospheric"]
    },

    # ------------------ AIR QUALITY & ENVIRONMENT ------------------
    "openaq": {
        "name": "OpenAQ Global Air Quality API",
        "type": "api",
        "category": "Air Quality",
        "purpose": "Real-time and historical PM2.5, PM10, ozone, and CO air pollution data worldwide",
        "official_url": "https://openaq.org/",
        "documentation_url": "https://docs.openaq.org/",
        "api_key_url": "https://explore.openaq.org/register",
        "download_url": "https://openaq.org/#/locations",
        "authentication_required": True,
        "pricing_information": "Free (Open Access)",
        "verification_status": "Verified",
        "keywords": ["air quality", "pollution", "pm2.5", "pm10", "environment", "aqi", "smog", "emissions"]
    },
    "waqi": {
        "name": "World Air Quality Index (WAQI) API",
        "type": "api",
        "category": "Air Quality",
        "purpose": "Global station-level real-time Air Quality Index readings and heatmaps",
        "official_url": "https://waqi.info/",
        "documentation_url": "https://aqicn.org/api/",
        "api_key_url": "https://aqicn.org/data-platform/token/",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free for Students & Researchers",
        "verification_status": "Verified",
        "keywords": ["aqi", "air pollution", "air index", "atmosphere", "waqi"]
    },

    # ------------------ MAPS, GEOCODING & NAVIGATION ------------------
    "openstreetmap": {
        "name": "OpenStreetMap Nominatim Geocoding API",
        "type": "api",
        "category": "Maps & Location",
        "purpose": "Address lookup, reverse geocoding, and map coordinate resolution",
        "official_url": "https://nominatim.openstreetmap.org/",
        "documentation_url": "https://nominatim.org/release-docs/latest/api/Overview/",
        "api_key_url": None,
        "download_url": None,
        "authentication_required": False,
        "pricing_information": "Free (Open Source)",
        "verification_status": "Verified",
        "keywords": ["map", "location", "geocoding", "coordinates", "gps", "routing", "places", "address", "navigation"]
    },
    "mapbox": {
        "name": "Mapbox Navigation & Maps API",
        "type": "api",
        "category": "Maps & Location",
        "purpose": "Interactive vector maps, route direction calculations, and turn-by-turn navigation",
        "official_url": "https://www.mapbox.com/",
        "documentation_url": "https://docs.mapbox.com/api/",
        "api_key_url": "https://account.mapbox.com/auth/signup/",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available (50,000 requests/mo)",
        "verification_status": "Verified",
        "keywords": ["maps", "routes", "tracking", "geolocation", "directions", "transit"]
    },

    # ------------------ AI, SPEECH & COMPUTER VISION ------------------
    "gemini_api": {
        "name": "Google Gemini API",
        "type": "api",
        "category": "AI & Language",
        "purpose": "Multimodal reasoning, text generation, code analysis, and document parsing",
        "official_url": "https://ai.google.dev/",
        "documentation_url": "https://ai.google.dev/gemini-api/docs",
        "api_key_url": "https://aistudio.google.com/app/apikey",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available",
        "verification_status": "Verified",
        "keywords": ["llm", "gemini", "generative ai", "multimodal", "chatbot", "nlp", "summarization", "ai assistant"]
    },
    "huggingface_api": {
        "name": "Hugging Face Serverless Inference API",
        "type": "api",
        "category": "Machine Learning",
        "purpose": "Instant cloud inference for 100,000+ open-source NLP, computer vision, and audio models",
        "official_url": "https://huggingface.co/",
        "documentation_url": "https://huggingface.co/docs/api-inference/index",
        "api_key_url": "https://huggingface.co/settings/tokens",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Community Tier",
        "verification_status": "Verified",
        "keywords": ["transformer", "bert", "sentiment", "hugging face", "classification", "speech recognition", "vision"]
    },
    "whisper_speech": {
        "name": "OpenAI Whisper Speech Recognition",
        "type": "ai_tool",
        "category": "Speech & Audio",
        "purpose": "Acoustic speech-to-text transcription and voice command translation",
        "official_url": "https://github.com/openai/whisper",
        "documentation_url": "https://github.com/openai/whisper#readme",
        "api_key_url": None,
        "download_url": "https://pypi.org/project/openai-whisper/",
        "authentication_required": False,
        "pricing_information": "Free Open Source (MIT)",
        "verification_status": "Verified",
        "keywords": ["voice", "speech", "whisper", "audio", "acoustic", "attendance", "transcription", "microphone"]
    },

    # ------------------ PAYMENTS & BILLING ------------------
    "stripe": {
        "name": "Stripe Payments API (Sandbox / Test Mode)",
        "type": "api",
        "category": "Payments",
        "purpose": "Payment processing, customer billing, and simulated test credit card checkout",
        "official_url": "https://stripe.com/",
        "documentation_url": "https://stripe.com/docs/api",
        "api_key_url": "https://dashboard.stripe.com/register",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free in Developer Test Mode",
        "verification_status": "Verified",
        "keywords": ["payment", "stripe", "checkout", "transaction", "billing", "ecommerce", "subscription", "credit card"]
    },
    "razorpay": {
        "name": "Razorpay Payment Gateway API",
        "type": "api",
        "category": "Payments",
        "purpose": "UPI, cards, and netbanking payment gateway for college events and student projects",
        "official_url": "https://razorpay.com/",
        "documentation_url": "https://razorpay.com/docs/api/",
        "api_key_url": "https://dashboard.razorpay.com/signup",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Developer Sandbox",
        "verification_status": "Verified",
        "keywords": ["razorpay", "upi", "rupee", "payment", "event registration", "tickets"]
    },

    # ------------------ AUTHENTICATION & IDENTITY ------------------
    "firebase_auth": {
        "name": "Google Firebase Authentication",
        "type": "api",
        "category": "Authentication",
        "purpose": "Secure email/password, Google OAuth, and phone OTP login workflows",
        "official_url": "https://firebase.google.com/products/auth",
        "documentation_url": "https://firebase.google.com/docs/auth",
        "api_key_url": "https://console.firebase.google.com/",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Spark Plan",
        "verification_status": "Verified",
        "keywords": ["authentication", "auth", "login", "oauth", "jwt", "firebase", "signup", "role"]
    },
    "supabase_auth": {
        "name": "Supabase Auth & Database",
        "type": "api",
        "category": "Authentication",
        "purpose": "PostgreSQL-backed user authentication, row-level security, and JWT sessions",
        "official_url": "https://supabase.com/auth",
        "documentation_url": "https://supabase.com/docs/guides/auth",
        "api_key_url": "https://supabase.com/dashboard/sign-up",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available",
        "verification_status": "Verified",
        "keywords": ["supabase", "postgres", "auth", "database", "backend as a service"]
    },

    # ------------------ NOTIFICATIONS, EMAIL & SMS ------------------
    "twilio": {
        "name": "Twilio Messaging API",
        "type": "api",
        "category": "Communications",
        "purpose": "Programmatic SMS alerts, OTP verification codes, and WhatsApp messages",
        "official_url": "https://www.twilio.com/",
        "documentation_url": "https://www.twilio.com/docs/sms",
        "api_key_url": "https://www.twilio.com/try-twilio",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Trial Credits Provided",
        "verification_status": "Verified",
        "keywords": ["sms", "twilio", "otp", "message", "whatsapp", "phone", "notification"]
    },
    "sendgrid": {
        "name": "SendGrid Email API",
        "type": "api",
        "category": "Communications",
        "purpose": "Transactional email delivery, password reset links, and confirmation receipts",
        "official_url": "https://sendgrid.com/",
        "documentation_url": "https://docs.sendgrid.com/api-reference",
        "api_key_url": "https://signup.sendgrid.com/",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Plan (100 emails/day)",
        "verification_status": "Verified",
        "keywords": ["email", "smtp", "sendgrid", "mailer", "newsletter", "receipt"]
    },

    # ------------------ GOVERNMENT, FINANCIAL & PUBLIC DATA ------------------
    "datagov": {
        "name": "Data.gov Open Data API",
        "type": "api",
        "category": "Public Data",
        "purpose": "Direct programmatic query access to 250,000+ official US federal datasets",
        "official_url": "https://data.gov/",
        "documentation_url": "https://api.data.gov/",
        "api_key_url": "https://api.data.gov/signup/",
        "download_url": "https://catalog.data.gov/dataset",
        "authentication_required": True,
        "pricing_information": "Free Public Domain",
        "verification_status": "Official Source",
        "keywords": ["government", "data.gov", "census", "education", "public data", "civic"]
    },
    "world_bank": {
        "name": "World Bank Open Data API",
        "type": "api",
        "category": "Public Data",
        "purpose": "Global economic indicators, climate data, GDP, population, and development statistics",
        "official_url": "https://data.worldbank.org/",
        "documentation_url": "https://datahelpdesk.worldbank.org/knowledgebase/topics/12558-developer-information",
        "api_key_url": None,
        "download_url": "https://data.worldbank.org/",
        "authentication_required": False,
        "pricing_information": "Free (No Key Required)",
        "verification_status": "Official Source",
        "keywords": ["world bank", "economy", "population", "indicators", "global", "poverty", "gdp"]
    },
    "alphavantage": {
        "name": "Alpha Vantage Financial Markets API",
        "type": "api",
        "category": "Finance",
        "purpose": "Historical stock prices, forex exchange rates, and crypto market indicators",
        "official_url": "https://www.alphavantage.co/",
        "documentation_url": "https://www.alphavantage.co/documentation/",
        "api_key_url": "https://www.alphavantage.co/support/#api-key",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier (25 requests/day)",
        "verification_status": "Verified",
        "keywords": ["finance", "stock", "crypto", "trading", "forex", "market", "prices", "ticker"]
    },

    # ==========================================================================
    # DATASETS (Official repositories, downloads & documentation)
    # ==========================================================================
    "kaggle_weather": {
        "name": "Historical Weather & Climate Forecast Dataset (CSV)",
        "type": "dataset",
        "category": "Weather",
        "purpose": "10-year historical daily and hourly weather observations for training ML models",
        "official_url": "https://www.kaggle.com/datasets/muthuj7/weather-dataset",
        "documentation_url": "https://www.kaggle.com/datasets/muthuj7/weather-dataset",
        "api_key_url": None,
        "download_url": "https://www.kaggle.com/datasets/muthuj7/weather-dataset/download?datasetVersionNumber=1",
        "authentication_required": True,  # Kaggle login
        "pricing_information": "Free Open Dataset",
        "verification_status": "Verified",
        "keywords": ["weather", "temperature", "humidity", "rain", "climate", "forecast"]
    },
    "kaggle_air_quality": {
        "name": "Global Air Pollution & AQI Dataset (CSV / Excel)",
        "type": "dataset",
        "category": "Air Quality",
        "purpose": "Historical PM2.5, PM10, NO2, and AQI pollution measurements across 150+ major cities",
        "official_url": "https://www.kaggle.com/datasets/hasibalmuzzamil/air-quality-dataset",
        "documentation_url": "https://www.kaggle.com/datasets/hasibalmuzzamil/air-quality-dataset",
        "api_key_url": None,
        "download_url": "https://www.kaggle.com/datasets/hasibalmuzzamil/air-quality-dataset/download?datasetVersionNumber=1",
        "authentication_required": True,
        "pricing_information": "Free Open Dataset",
        "verification_status": "Verified",
        "keywords": ["air quality", "pollution", "pm2.5", "aqi", "smog", "air"]
    },
    "uci_student_performance": {
        "name": "UCI Student Academic Performance Dataset (CSV)",
        "type": "dataset",
        "category": "Education",
        "purpose": "Demographic, social, and academic progress indicators for predicting student success",
        "official_url": "https://archive.ics.uci.edu/dataset/320/student+performance",
        "documentation_url": "https://archive.ics.uci.edu/dataset/320/student+performance",
        "api_key_url": None,
        "download_url": "https://archive.ics.uci.edu/static/public/320/student+performance.zip",
        "authentication_required": False,
        "pricing_information": "Free (Public Domain / CC-BY)",
        "verification_status": "Official Source",
        "keywords": ["student", "academic", "performance", "grade", "education", "dropout", "exam", "attendance"]
    },
    "kaggle_credit_fraud": {
        "name": "Credit Card Fraud Detection Dataset (CSV)",
        "type": "dataset",
        "category": "Finance",
        "purpose": "284,807 anonymized financial transactions with PCA features for anomaly detection",
        "official_url": "https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud",
        "documentation_url": "https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud",
        "api_key_url": None,
        "download_url": "https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud/download?datasetVersionNumber=3",
        "authentication_required": True,
        "pricing_information": "Free Open Dataset",
        "verification_status": "Verified",
        "keywords": ["fraud", "credit card", "finance", "anomaly", "banking", "transaction"]
    },
    "huggingface_sentiment": {
        "name": "IMDb / Tweet Sentiment Classification Dataset (JSON / Arrow)",
        "type": "dataset",
        "category": "NLP",
        "purpose": "Labeled text corpus for training sentiment analysis, topic detection, and review classification",
        "official_url": "https://huggingface.co/datasets/stanfordnlp/imdb",
        "documentation_url": "https://huggingface.co/docs/datasets",
        "api_key_url": None,
        "download_url": "https://huggingface.co/datasets/stanfordnlp/imdb/resolve/main/data/train-00000-of-00001.parquet",
        "authentication_required": False,
        "pricing_information": "Free Open Source",
        "verification_status": "Verified",
        "keywords": ["sentiment", "imdb", "nlp", "text", "reviews", "twitter", "tweets", "classification"]
    },
    "kaggle_ecommerce": {
        "name": "E-Commerce Customer Behavior & Transactions Dataset (CSV)",
        "type": "dataset",
        "category": "E-Commerce",
        "purpose": "Order logs, product catalogs, customer reviews, and churn indicators",
        "official_url": "https://www.kaggle.com/datasets/carrie1/ecommerce-data",
        "documentation_url": "https://www.kaggle.com/datasets/carrie1/ecommerce-data",
        "api_key_url": None,
        "download_url": "https://www.kaggle.com/datasets/carrie1/ecommerce-data/download?datasetVersionNumber=1",
        "authentication_required": True,
        "pricing_information": "Free Open Dataset",
        "verification_status": "Verified",
        "keywords": ["ecommerce", "sales", "store", "orders", "churn", "retail", "products"]
    },
    "google_dataset_search": {
        "name": "Google Dataset Search Repository",
        "type": "dataset",
        "category": "General Datasets",
        "purpose": "Search engine indexing tens of millions of open research datasets across scientific repositories",
        "official_url": "https://datasetsearch.research.google.com/",
        "documentation_url": "https://research.google/pubs/google-dataset-search-building-a-search-engine-for-datasets-in-the-wild/",
        "api_key_url": None,
        "download_url": "https://datasetsearch.research.google.com/",
        "authentication_required": False,
        "pricing_information": "Free",
        "verification_status": "Verified",
        "keywords": ["dataset", "csv", "data", "repository", "research", "download"]
    },

    # ==========================================================================
    # SMART AI TOOLS (Coding, UI/UX, DB, Testing, Docs, Research)
    # ==========================================================================
    "gemini_assistant": {
        "name": "Google Gemini",
        "type": "ai_tool",
        "category": "Coding",
        "purpose": "Full-stack code generation, refactoring, and complex bug troubleshooting",
        "official_url": "https://gemini.google.com/",
        "documentation_url": "https://ai.google.dev/gemini-api/docs",
        "api_key_url": "https://aistudio.google.com/app/apikey",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available",
        "verification_status": "Verified",
        "keywords": ["code", "coding", "python", "flask", "backend", "frontend", "programming"]
    },
    "chatgpt": {
        "name": "ChatGPT (OpenAI)",
        "type": "ai_tool",
        "category": "Coding & Research",
        "purpose": "Architecture planning, step-by-step programming, and academic viva preparation",
        "official_url": "https://chatgpt.com/",
        "documentation_url": "https://platform.openai.com/docs",
        "api_key_url": "https://platform.openai.com/api-keys",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available",
        "verification_status": "Verified",
        "keywords": ["chatgpt", "openai", "code", "assistant", "research"]
    },
    "claude": {
        "name": "Claude AI (Anthropic)",
        "type": "ai_tool",
        "category": "Coding & Architecture",
        "purpose": "Deep code analysis, refactoring large modules, and technical design verification",
        "official_url": "https://claude.ai/",
        "documentation_url": "https://docs.anthropic.com/",
        "api_key_url": "https://console.anthropic.com/",
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available",
        "verification_status": "Verified",
        "keywords": ["claude", "anthropic", "code", "refactoring", "architecture"]
    },
    "perplexity": {
        "name": "Perplexity AI",
        "type": "ai_tool",
        "category": "Research",
        "purpose": "Academic literature search, technology benchmarking, and citation discovery",
        "official_url": "https://www.perplexity.ai/",
        "documentation_url": "https://docs.perplexity.ai/",
        "api_key_url": None,
        "download_url": None,
        "authentication_required": False,
        "pricing_information": "Free Search Engine",
        "verification_status": "Verified",
        "keywords": ["research", "literature", "citations", "survey", "papers", "benchmarks"]
    },
    "figma_ai": {
        "name": "Figma AI & Wireframing",
        "type": "ai_tool",
        "category": "UI/UX",
        "purpose": "Interactive web & mobile mockup design, design systems, and responsive wireframing",
        "official_url": "https://www.figma.com/",
        "documentation_url": "https://help.figma.com/hc/en-us",
        "api_key_url": None,
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Student Plan Available",
        "verification_status": "Verified",
        "keywords": ["ui", "ux", "figma", "wireframe", "prototype", "design", "mockup", "interface"]
    },
    "v0_dev": {
        "name": "v0 by Vercel",
        "type": "ai_tool",
        "category": "UI/UX",
        "purpose": "Prompt-to-UI component generator using React, Tailwind CSS, and HTML",
        "official_url": "https://v0.dev/",
        "documentation_url": "https://v0.dev/docs",
        "api_key_url": None,
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available",
        "verification_status": "Verified",
        "keywords": ["ui", "tailwind", "react", "html", "css", "component", "frontend"]
    },
    "eraser_io": {
        "name": "Eraser.io Diagram & Schema AI",
        "type": "ai_tool",
        "category": "Database & Architecture",
        "purpose": "Prompt-based Entity Relationship Diagrams (ERD) and architecture flowcharts",
        "official_url": "https://www.eraser.io/",
        "documentation_url": "https://docs.eraser.io/",
        "api_key_url": None,
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available",
        "verification_status": "Verified",
        "keywords": ["database", "schema", "erd", "architecture", "flowchart", "diagram", "sql"]
    },
    "prisma_studio": {
        "name": "Prisma Studio & Schema Builder",
        "type": "ai_tool",
        "category": "Database",
        "purpose": "Visual database modeling, relation mapping, and SQL query inspection",
        "official_url": "https://www.prisma.io/studio",
        "documentation_url": "https://www.prisma.io/docs/concepts/components/prisma-studio",
        "api_key_url": None,
        "download_url": "https://www.npmjs.com/package/@prisma/studio",
        "authentication_required": False,
        "pricing_information": "Free Open Source",
        "verification_status": "Verified",
        "keywords": ["database", "sqlite", "postgres", "sql", "orm", "relations", "tables"]
    },
    "postman_ai": {
        "name": "Postman API Platform & AI Assistant",
        "type": "ai_tool",
        "category": "Testing & APIs",
        "purpose": "REST API testing, automated endpoint assertions, collection runners, and mock servers",
        "official_url": "https://www.postman.com/",
        "documentation_url": "https://learning.postman.com/docs/introduction/overview/",
        "api_key_url": None,
        "download_url": "https://www.postman.com/downloads/",
        "authentication_required": True,
        "pricing_information": "Free Plan Available",
        "verification_status": "Verified",
        "keywords": ["test", "testing", "api testing", "postman", "endpoints", "assert", "mock"]
    },
    "mintlify": {
        "name": "Mintlify AI Documentation",
        "type": "ai_tool",
        "category": "Documentation",
        "purpose": "Automated code docstrings, API reference docs, and academic project README generator",
        "official_url": "https://mintlify.com/",
        "documentation_url": "https://mintlify.com/docs/quickstart",
        "api_key_url": None,
        "download_url": None,
        "authentication_required": True,
        "pricing_information": "Free Tier Available",
        "verification_status": "Verified",
        "keywords": ["docs", "documentation", "readme", "report", "srs", "markdown", "viva"]
    }
}


class ResourceFinderService:
    """Intelligent Resource Finder, Gemini analyzer, and Verification Engine."""

    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        self.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # ==========================================================================
    # 1. GEMINI PROJECT ANALYSIS
    # ==========================================================================
    def analyze_project_requirements(
        self,
        title: str,
        description: str,
        domain: str = "Web Development",
        technologies: str = "",
        objective: str = "",
        existing_tasks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Sends project metadata to Gemini to analyze technical resource needs.
        Returns strictly structured JSON identifying resource requirements without hallucinating URLs.
        """
        tasks_snippet = ""
        if existing_tasks:
            tasks_snippet = "\nEXISTING PLANNED TASKS:\n" + "\n".join([f"- {t}" for t in existing_tasks[:10]])

        prompt = f"""You are an expert AI Software Architect and Academic Project Resource Evaluator.
Analyze the following academic engineering project and determine its exact resource and data requirements.

PROJECT DETAILS:
- Title: {title}
- Description: {description}
- Domain: {domain}
- Selected / Known Technologies: {technologies or "Standard full-stack tools"}
- Project Objective / Requirements: {objective or "Build and deploy an academic prototype."}
{tasks_snippet}

ANALYZE THE FOLLOWING:
1. What type of project is this? (e.g., Software, Machine Learning, Web App, IoT, Mobile App)
2. Is it software-related? (true/false)
3. Which technologies may be required?
4. Does this project need external APIs? (e.g. weather, maps, payments, auth, air quality, SMS)
5. Does this project need datasets? (e.g. historical CSV records, images, sensor logs)
6. Does this project need CSV files or other downloadable data?
7. Does this project need AI tools? (for coding, UI design, database schema, testing, docs)
8. Which specific external resources are required to successfully complete this project?

CRITICAL RULES:
- DO NOT invent, hallucinate, or guess website URLs!
- You must identify WHAT resource is needed, WHY it is needed, its category, and a suggested search requirement.
- The backend will look up and verify official links.

Return ONLY valid JSON matching this exact schema:
{{
  "project_type": "Software + Machine Learning",
  "is_software": true,
  "categories": ["Web Development", "Machine Learning", "Data Analysis"],
  "needs_external_apis": true,
  "needs_datasets": true,
  "needs_downloadable_data": true,
  "needs_ai_tools": true,
  "suggested_technologies": ["Python", "Flask", "Scikit-Learn", "PostgreSQL"],
  "resources_needed": [
    {{
      "type": "api",
      "category": "Weather",
      "suggested_name": "Weather Data API",
      "purpose": "Real-time weather data",
      "description": "Weather data is required as an input for the prediction model.",
      "search_query": "official free weather API real time historical data",
      "required": true
    }},
    {{
      "type": "dataset",
      "category": "Historical Data",
      "suggested_name": "Historical Climate Dataset",
      "purpose": "Historical weather observations",
      "description": "Historical data is required for training the ML model.",
      "search_query": "official historical weather dataset CSV download",
      "required": true
    }}
  ],
  "ai_tools_needed": [
    {{
      "category": "Coding",
      "purpose": "Backend REST API implementation",
      "tool_suggestion": "Gemini / ChatGPT"
    }},
    {{
      "category": "Database",
      "purpose": "Relational schema and ERD design",
      "tool_suggestion": "Eraser.io / Prisma Studio"
    }}
  ]
}}
"""
        # 1. Try Gemini API
        if self.gemini_key:
            try:
                res_text = self._call_gemini_api(prompt)
                parsed = self._extract_json(res_text)
                if parsed and isinstance(parsed, dict) and "resources_needed" in parsed:
                    return parsed
            except Exception as e:
                logger.warning(f"Gemini API call failed during resource analysis: {e}. Falling back to rule engine.")

        # 2. Domain-aware intelligent rule-based analyzer
        return self._generate_rule_based_resource_analysis(
            title=title,
            description=description,
            domain=domain,
            technologies=technologies,
            objective=objective
        )

    # ==========================================================================
    # 2. BACKEND RESOURCE VERIFICATION & MATCHING ENGINE
    # ==========================================================================
    def resolve_and_verify_resources(
        self,
        analysis: Dict[str, Any],
        project_title: str,
        project_domain: str
    ) -> List[Dict[str, Any]]:
        """
        Takes Gemini's identified requirements, matches them against known official
        providers or verified sources, validates URLs, and assigns verification statuses.
        """
        verified_results: List[Dict[str, Any]] = []
        seen_names = set()

        # A. Resolve Gemini's identified resource items
        items = analysis.get("resources_needed", [])
        for item in items:
            rtype = (item.get("type") or "api").lower().strip()
            purpose = item.get("purpose") or ""
            desc = item.get("description") or ""
            search_query = item.get("search_query") or ""
            category = item.get("category") or ""
            suggested_name = item.get("suggested_name") or ""

            match = self._find_best_catalog_match(
                rtype=rtype,
                query=f"{suggested_name} {purpose} {category} {search_query}".lower()
            )

            if match:
                res_key = match["name"]
                if res_key in seen_names:
                    continue
                seen_names.add(res_key)

                verified_results.append({
                    "resource_name": match["name"],
                    "resource_type": match["type"],
                    "purpose": purpose or match["purpose"],
                    "description": desc or match["purpose"],
                    "why_needed": desc or f"Essential {match['type'].upper()} for {project_title}.",
                    "official_url": self._sanitize_url(match.get("official_url")),
                    "documentation_url": self._sanitize_url(match.get("documentation_url")),
                    "api_key_url": self._sanitize_url(match.get("api_key_url")),
                    "download_url": self._sanitize_url(match.get("download_url")),
                    "authentication_required": match.get("authentication_required", False),
                    "pricing_information": match.get("pricing_information", "Free Tier Available"),
                    "verification_status": match.get("verification_status", "Verified")
                })

        # B. Ensure core domain essentials are present (e.g. if weather project, ensure weather dataset & API)
        domain_essentials = self._get_domain_essentials(project_title, project_domain)
        for cand in domain_essentials:
            if cand["name"] not in seen_names:
                seen_names.add(cand["name"])
                verified_results.append({
                    "resource_name": cand["name"],
                    "resource_type": cand["type"],
                    "purpose": cand["purpose"],
                    "description": cand["purpose"],
                    "why_needed": f"Required {cand['type'].upper()} deliverable for {project_title}.",
                    "official_url": self._sanitize_url(cand.get("official_url")),
                    "documentation_url": self._sanitize_url(cand.get("documentation_url")),
                    "api_key_url": self._sanitize_url(cand.get("api_key_url")),
                    "download_url": self._sanitize_url(cand.get("download_url")),
                    "authentication_required": cand.get("authentication_required", False),
                    "pricing_information": cand.get("pricing_information", "Free Tier Available"),
                    "verification_status": cand.get("verification_status", "Verified")
                })

        return verified_results

    # ==========================================================================
    # 3. CONTEXTUAL SMART AI TOOL ADVISOR & PROMPT GENERATOR
    # ==========================================================================
    def generate_ai_tool_recommendations(
        self,
        project: Project,
        tasks: Optional[List[Task]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recommends AI tools tailored specifically to the student's project across
        Research, Coding, Debugging, UI/UX, Database, Documentation, and Testing,
        along with custom, ready-to-use prompts.
        """
        title = project.project_name
        domain = project.domain
        tech = project.technologies or "Python, Flask, PostgreSQL, HTML5, Bootstrap 5"

        task_titles = [t.title for t in tasks] if tasks else []
        task_str = ", ".join(task_titles[:5]) if task_titles else "Core system modules"

        recommendations: List[Dict[str, Any]] = [
            # 1. Research
            {
                "tool_name": "Perplexity AI",
                "purpose": "Research & Literature Survey",
                "reason": f"Discovers academic IEEE/ACM literature, similar published architectures, and benchmarks relevant to {title}.",
                "official_url": "https://www.perplexity.ai/",
                "documentation_url": "https://docs.perplexity.ai/",
                "generated_prompt": (
                    f"I am an engineering student developing '{title}' in the domain of {domain}. "
                    f"Provide an academic literature survey of current state-of-the-art implementations, "
                    f"standard evaluation metrics, and key technical challenges students face when implementing "
                    f"systems using {tech}. Include IEEE/Springer citation pointers."
                ),
                "verification_status": "Verified"
            },
            # 2. Coding
            {
                "tool_name": "Google Gemini / ChatGPT",
                "purpose": "Coding & Backend Implementation",
                "reason": f"Accelerates writing clean, modular REST API blueprints, authentication handlers, and core business logic in {tech}.",
                "official_url": "https://gemini.google.com/",
                "documentation_url": "https://ai.google.dev/gemini-api/docs",
                "generated_prompt": (
                    f"I am building '{title}' using {tech}. Help me implement the core server logic for: {task_str}. "
                    f"First analyze the requirements and database models, then provide clean, modular, production-ready "
                    f"code with docstrings and input validation. Do not modify unrelated modules."
                ),
                "verification_status": "Verified"
            },
            # 3. Debugging
            {
                "tool_name": "Cursor AI / Claude",
                "purpose": "Debugging & Error Resolution",
                "reason": "Pinpoints edge-case runtime exceptions, traceback root-causes, and SQL transaction deadlocks.",
                "official_url": "https://claude.ai/",
                "documentation_url": "https://docs.anthropic.com/",
                "generated_prompt": (
                    f"I encountered a bug in my '{title}' application built with {tech}. "
                    f"Here is the traceback and code snippet: [PASTE ERROR HERE]. "
                    f"Explain the exact root cause, explain why it happened, and provide the minimal drop-in replacement "
                    f"fix preserving my existing data structures."
                ),
                "verification_status": "Verified"
            },
            # 4. UI/UX
            {
                "tool_name": "v0 by Vercel / Figma AI",
                "purpose": "UI/UX & Frontend Wireframing",
                "reason": f"Creates intuitive student and administrator interfaces, dashboards, and responsive forms tailored for {title}.",
                "official_url": "https://v0.dev/",
                "documentation_url": "https://v0.dev/docs",
                "generated_prompt": (
                    f"Design a modern, responsive web dashboard UI for '{title}' using Bootstrap 5 and clean cards. "
                    f"Include navigation, KPI summary cards, status badges, and action buttons for completing project tasks. "
                    f"Keep the interface clean and accessible."
                ),
                "verification_status": "Verified"
            },
            # 5. Database
            {
                "tool_name": "Eraser.io / Prisma Studio",
                "purpose": "Database & Relational Schema Design",
                "reason": "Generates normalized SQL tables, primary/foreign key indexes, and Entity Relationship Diagrams (ERD).",
                "official_url": "https://www.eraser.io/",
                "documentation_url": "https://docs.eraser.io/",
                "generated_prompt": (
                    f"Act as a Principal Database Architect. Design a fully normalized 3NF relational SQL database schema for '{title}'. "
                    f"Technologies: {tech}. Provide all CREATE TABLE statements with foreign keys, ON DELETE CASCADE constraints, "
                    f"indexes on query lookup columns, and seed records for testing."
                ),
                "verification_status": "Verified"
            },
            # 6. Documentation
            {
                "tool_name": "Mintlify / Overleaf",
                "purpose": "Documentation & Academic Report",
                "reason": "Generates thesis chapter abstracts, system requirements specifications (SRS), and viva presentation slides.",
                "official_url": "https://mintlify.com/",
                "documentation_url": "https://mintlify.com/docs",
                "generated_prompt": (
                    f"Write a formal academic Software Requirements Specification (SRS) and project report abstract for '{title}'. "
                    f"Domain: {domain}. Include Problem Statement, Objectives, Proposed System Architecture ({tech}), "
                    f"Hardware/Software Requirements, and expected project outcomes suitable for college faculty evaluation."
                ),
                "verification_status": "Verified"
            },
            # 7. Testing
            {
                "tool_name": "Postman AI / Pytest",
                "purpose": "Automated Testing & Quality Assurance",
                "reason": f"Generates automated test suites, HTTP endpoint validation tests, and boundary value edge-case assertions.",
                "official_url": "https://www.postman.com/",
                "documentation_url": "https://learning.postman.com/docs/",
                "generated_prompt": (
                    f"Generate a comprehensive automated Pytest test suite for '{title}' backend APIs ({tech}). "
                    f"Cover: 1) Happy path requests with HTTP 200/201, 2) Missing field validation with HTTP 400, "
                    f"3) Unauthorized access with HTTP 403, and 4) Database boundary condition edge cases."
                ),
                "verification_status": "Verified"
            }
        ]

        return recommendations

    # ==========================================================================
    # 4. TASK GENERATION INTEGRATION (MAP RESOURCES TO SPECIFIC TASKS)
    # ==========================================================================
    def map_resources_to_tasks(
        self,
        tasks: List[Task],
        resources: List[ProjectResource]
    ) -> None:
        """
        Associates each project task with the relevant API, dataset, or AI tool
        based on category, keyword match, and task objectives.
        """
        for task in tasks:
            t_title = (task.title or "").lower()
            t_cat = (task.category or "").lower()
            t_desc = (task.description or "").lower()
            combined = f"{t_title} {t_cat} {t_desc}"

            for res in resources:
                r_name = res.resource_name.lower()
                r_purp = (res.purpose or "").lower()
                r_type = res.resource_type.lower()

                should_link = False

                if r_type == "dataset" and ("dataset" in combined or "train" in combined or "model" in combined or "data" in combined):
                    should_link = True
                elif "weather" in r_name and "weather" in combined:
                    should_link = True
                elif "air" in r_name and ("air" in combined or "pollution" in combined or "aqi" in combined):
                    should_link = True
                elif "map" in r_name and ("map" in combined or "gps" in combined or "location" in combined or "route" in combined):
                    should_link = True
                elif "auth" in r_name and ("auth" in combined or "login" in combined or "user" in combined or "rbac" in combined):
                    should_link = True
                elif "speech" in r_name or "whisper" in r_name:
                    if "voice" in combined or "speech" in combined or "audio" in combined or "attendance" in combined:
                        should_link = True
                elif "database" in t_cat and ("db" in r_name or "schema" in r_name or "prisma" in r_name):
                    should_link = True
                elif "test" in t_cat and ("postman" in r_name or "test" in r_name):
                    should_link = True
                elif "documentation" in t_cat and ("doc" in r_name or "mintlify" in r_name or "report" in r_name):
                    should_link = True

                if should_link and res.task_id is None:
                    res.task_id = task.id

    # ==========================================================================
    # 5. DATABASE PERSISTENCE & DE-DUPLICATION
    # ==========================================================================
    def analyze_and_store_project_resources(
        self,
        project: Project,
        tasks: Optional[List[Task]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates full analysis, verification, database persistence, and task mapping.
        Avoids creating duplicate resources.
        """
        existing_tasks = [t.title for t in tasks] if tasks else [t.title for t in project.tasks.all()]

        # 1. Run Gemini Analysis
        analysis = self.analyze_project_requirements(
            title=project.project_name,
            description=project.description or project.project_summary or "",
            domain=project.domain,
            technologies=project.technologies or "",
            objective=project.objective or "",
            existing_tasks=existing_tasks
        )

        # 2. Resolve and verify official resources
        resolved_resources = self.resolve_and_verify_resources(
            analysis=analysis,
            project_title=project.project_name,
            project_domain=project.domain
        )

        # 3. Store ProjectResource entities (avoiding duplicates)
        saved_resources = []
        for rdata in resolved_resources:
            existing = ProjectResource.query.filter_by(
                project_id=project.id,
                resource_name=rdata["resource_name"]
            ).first()

            if not existing:
                res = ProjectResource(
                    project_id=project.id,
                    resource_name=rdata["resource_name"],
                    resource_type=rdata["resource_type"],
                    purpose=rdata["purpose"],
                    description=rdata["description"],
                    why_needed=rdata["why_needed"],
                    official_url=rdata["official_url"],
                    documentation_url=rdata["documentation_url"],
                    api_key_url=rdata["api_key_url"],
                    download_url=rdata["download_url"],
                    authentication_required=rdata["authentication_required"],
                    pricing_information=rdata["pricing_information"],
                    verification_status=rdata["verification_status"]
                )
                db.session.add(res)
                saved_resources.append(res)
            else:
                existing.official_url = rdata["official_url"]
                existing.documentation_url = rdata["documentation_url"]
                existing.api_key_url = rdata["api_key_url"]
                existing.download_url = rdata["download_url"]
                existing.verification_status = rdata["verification_status"]
                saved_resources.append(existing)

        db.session.commit()

        # 4. Generate AI Recommendations & Prompts
        ai_tools_list = self.generate_ai_tool_recommendations(project, tasks)
        for tdata in ai_tools_list:
            existing_tool = AIRecommendation.query.filter_by(
                project_id=project.id,
                purpose=tdata["purpose"]
            ).first()

            if not existing_tool:
                rec = AIRecommendation(
                    project_id=project.id,
                    tool_name=tdata["tool_name"],
                    purpose=tdata["purpose"],
                    reason=tdata["reason"],
                    official_url=tdata["official_url"],
                    documentation_url=tdata.get("documentation_url"),
                    generated_prompt=tdata["generated_prompt"],
                    verification_status=tdata.get("verification_status", "Verified")
                )
                db.session.add(rec)
            else:
                existing_tool.tool_name = tdata["tool_name"]
                existing_tool.reason = tdata["reason"]
                existing_tool.generated_prompt = tdata["generated_prompt"]

        db.session.commit()

        # 5. Map resources to tasks
        all_tasks = tasks or project.tasks.all()
        all_res = project.resources.all()
        if all_tasks and all_res:
            self.map_resources_to_tasks(all_tasks, all_res)
            db.session.commit()

        return {
            "status": "success",
            "project_id": project.id,
            "resources_count": len(all_res),
            "ai_tools_count": project.ai_recommendations.count()
        }

    # ==========================================================================
    # INTERNAL HELPERS & FALLBACKS
    # ==========================================================================
    def _find_best_catalog_match(self, rtype: str, query: str) -> Optional[Dict[str, Any]]:
        """Scans catalog entries to find best matching official resource."""
        best_match = None
        best_score = 0

        for key, entry in OFFICIAL_RESOURCES_CATALOG.items():
            score = 0
            if entry["type"] == rtype:
                score += 3

            for kw in entry.get("keywords", []):
                if kw in query:
                    score += 2

            if entry["name"].lower() in query:
                score += 5

            if score > best_score and score >= 3:
                best_score = score
                best_match = entry

        return best_match

    def _get_domain_essentials(self, title: str, domain: str) -> List[Dict[str, Any]]:
        """Provides default domain essentials if specific requirements were sparse."""
        t_low = title.lower()
        d_low = domain.lower()
        essentials = []

        if "weather" in t_low or "climate" in t_low:
            essentials.extend([
                OFFICIAL_RESOURCES_CATALOG["open_meteo"],
                OFFICIAL_RESOURCES_CATALOG["kaggle_weather"]
            ])
        elif "air" in t_low or "pollution" in t_low or "aqi" in t_low:
            essentials.extend([
                OFFICIAL_RESOURCES_CATALOG["openaq"],
                OFFICIAL_RESOURCES_CATALOG["kaggle_air_quality"]
            ])
        elif "voice" in t_low or "attendance" in t_low or "speech" in t_low:
            essentials.extend([
                OFFICIAL_RESOURCES_CATALOG["whisper_speech"],
                OFFICIAL_RESOURCES_CATALOG["uci_student_performance"]
            ])
        elif "student" in t_low or "education" in t_low or "academic" in t_low:
            essentials.extend([
                OFFICIAL_RESOURCES_CATALOG["uci_student_performance"],
                OFFICIAL_RESOURCES_CATALOG["firebase_auth"]
            ])
        elif "fraud" in t_low or "finance" in t_low or "stock" in t_low:
            essentials.extend([
                OFFICIAL_RESOURCES_CATALOG["alphavantage"],
                OFFICIAL_RESOURCES_CATALOG["kaggle_credit_fraud"]
            ])
        elif "ecommerce" in t_low or "store" in t_low or "shop" in t_low:
            essentials.extend([
                OFFICIAL_RESOURCES_CATALOG["stripe"],
                OFFICIAL_RESOURCES_CATALOG["kaggle_ecommerce"]
            ])
        elif "machine learning" in d_low or "ai" in d_low:
            essentials.extend([
                OFFICIAL_RESOURCES_CATALOG["huggingface_api"],
                OFFICIAL_RESOURCES_CATALOG["google_dataset_search"]
            ])
        else:
            essentials.extend([
                OFFICIAL_RESOURCES_CATALOG["firebase_auth"],
                OFFICIAL_RESOURCES_CATALOG["openstreetmap"]
            ])

        return essentials

    def _generate_rule_based_resource_analysis(
        self,
        title: str,
        description: str,
        domain: str,
        technologies: str,
        objective: str
    ) -> Dict[str, Any]:
        """High-precision offline fallback analyzing project domain and keywords."""
        t_low = title.lower() + " " + description.lower()
        is_software = True
        resources_needed = []

        if "weather" in t_low or "climate" in t_low or "forecast" in t_low:
            resources_needed.append({
                "type": "api",
                "category": "Weather",
                "suggested_name": "Open-Meteo Weather API",
                "purpose": "Real-time weather data & forecasts",
                "description": "Required to fetch temperature, precipitation, and wind speeds.",
                "search_query": "official free weather API real time historical data",
                "required": True
            })
            resources_needed.append({
                "type": "dataset",
                "category": "Weather",
                "suggested_name": "Historical Weather & Climate Forecast Dataset (CSV)",
                "purpose": "Historical weather observations for ML training",
                "description": "Required for training the weather prediction model.",
                "search_query": "official historical weather dataset CSV download",
                "required": True
            })
        elif "air" in t_low or "pollution" in t_low or "aqi" in t_low:
            resources_needed.append({
                "type": "api",
                "category": "Air Quality",
                "suggested_name": "OpenAQ Global Air Quality API",
                "purpose": "Real-time PM2.5 and AQI sensor readings",
                "description": "Required for air pollution data inputs.",
                "search_query": "official open air quality API real time",
                "required": True
            })
            resources_needed.append({
                "type": "dataset",
                "category": "Air Quality",
                "suggested_name": "Global Air Pollution & AQI Dataset (CSV / Excel)",
                "purpose": "Historical pollution data for model training",
                "description": "Required to train regression/classification models on historical AQI.",
                "search_query": "official air quality dataset CSV download",
                "required": True
            })
        elif "voice" in t_low or "speech" in t_low or "attendance" in t_low:
            resources_needed.append({
                "type": "ai_tool",
                "category": "Speech & Audio",
                "suggested_name": "OpenAI Whisper Speech Recognition",
                "purpose": "Voice command transcription & roll-call speech parsing",
                "description": "Required to convert student acoustic names into text entries.",
                "search_query": "official open source speech to text whisper",
                "required": True
            })
            resources_needed.append({
                "type": "dataset",
                "category": "Education",
                "suggested_name": "UCI Student Academic Performance Dataset (CSV)",
                "purpose": "Student attendance & performance records",
                "description": "Sample student rosters and attendance percentages.",
                "search_query": "official student attendance dataset CSV download",
                "required": False
            })
        else:
            resources_needed.append({
                "type": "api",
                "category": "Authentication",
                "suggested_name": "Google Firebase Authentication",
                "purpose": "Role-based user login & session management",
                "description": "Required for secure user authentication.",
                "search_query": "official firebase authentication developer docs",
                "required": True
            })
            resources_needed.append({
                "type": "dataset",
                "category": "General Datasets",
                "suggested_name": "Google Dataset Search Repository",
                "purpose": "Reference project training data",
                "description": "Search open CSV datasets matching project domain.",
                "search_query": "official dataset search open CSV downloads",
                "required": False
            })

        return {
            "project_type": "Software + Machine Learning" if ("ml" in t_low or "ai" in t_low) else "Software",
            "is_software": is_software,
            "categories": [domain, "Web Development"],
            "needs_external_apis": True,
            "needs_datasets": True,
            "needs_downloadable_data": True,
            "needs_ai_tools": True,
            "suggested_technologies": [t.strip() for t in technologies.split(",") if t.strip()] or ["Python", "Flask", "PostgreSQL"],
            "resources_needed": resources_needed,
            "ai_tools_needed": [
                {"category": "Coding", "purpose": "REST API Development", "tool_suggestion": "Google Gemini"},
                {"category": "Database", "purpose": "Database Design", "tool_suggestion": "Eraser.io"},
                {"category": "Testing", "purpose": "API Testing", "tool_suggestion": "Postman"}
            ]
        }

    def _call_gemini_api(self, prompt: str) -> str:
        """Invokes Gemini API via HTTP REST."""
        model_name = self.gemini_model or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_key}"

        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            candidates = body.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
        return ""

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Safely extracts JSON from model response text."""
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except Exception:
                    pass
        return {}

    def _sanitize_url(self, url: Optional[str]) -> Optional[str]:
        """Validates that a URL is a well-formed HTTP/HTTPS URL."""
        if not url:
            return None
        url = url.strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return url
        return None


# Global singleton instance
_resource_finder_instance = None


def get_resource_finder_service() -> ResourceFinderService:
    global _resource_finder_instance
    if _resource_finder_instance is None:
        _resource_finder_instance = ResourceFinderService()
    return _resource_finder_instance
