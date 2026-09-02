# PROJECTGUARD — AI-Based Student Project Failure Prediction & Early Warning System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-green.svg)](https://flask.palletsprojects.com/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.3%2B-orange.svg)](https://scikit-learn.org/)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0%2B-red.svg)](https://xgboost.readthedocs.io/)
[![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg)]()

> **"Know Your Project Risk Before It's Too Late."**  
> *ProjectGuard uses project progress data and machine learning to identify academic project risks early and provide actionable recommendations.*

---

## 1. Project Overview & Problem Statement

In academic environments, undergraduate and graduate engineering students frequently embark on multi-month capstone and mini-projects without early feedback on milestone velocity. Many realize too late that their project has fallen behind schedule, has high delayed tasks, insufficient testing coverage, poor documentation, or unaddressed bugs.

**ProjectGuard** acts as an **early-warning and project-risk monitoring platform**. It continuously evaluates project progression metrics through trained Machine Learning models to estimate failure/success probabilities, extract driving risk factors using Explainable AI (SHAP), generate supportive actionable recommendations, simulate hypothetical adjustments via a real-time **What-If Simulator**, and provide faculty advisors with cohort monitoring tools.

### Core Guiding Principle
The purpose of ProjectGuard is **never to discourage students** by stating "your project will fail." Instead, it probabilistically flags risks early and guides students with prioritized engineering steps to recover and succeed.

---

## 2. Key Features

- 🎯 **AI Project Failure Prediction**: Estimates Success Probability (%) and Failure Probability (%) using scikit-learn / XGBoost classifiers.
- 🚦 **Configurable Risk Classification**:
  - `0% – 20%` Failure Probability: **LOW RISK**
  - `21% – 40%` Failure Probability: **MODERATE RISK**
  - `41% – 60%` Failure Probability: **HIGH RISK**
  - `61% – 100%` Failure Probability: **CRITICAL RISK**
- 🔍 **Explainable AI (SHAP / Feature Attribution)**: Pinpoints exact risk drivers (e.g. testing lag behind progress, blocked tasks, high schedule pressure, defect density).
- 💡 **Actionable Recommendation Engine**: Supportive, prioritized engineering advice targeting bug triage, testing requirements, and scope management.
- 🎛️ **Interactive What-If Scenario Simulator**: Allows students to test hypothetical adjustments ("What if I finish 4 more tasks and boost testing to 60%?") using the real ML model without mutating stored project data.
- 📈 **Risk Progression Tracking**: Visualizes milestone risk history over time with interactive Chart.js line graphs.
- ⚠️ **Early Warning Alerts**: Automatically detects risk leaps ($\ge 15\%$) between consecutive evaluations and alerts students and advisors.
- 👨‍🏫 **Faculty Monitoring Dashboard**: Allows faculty advisors to filter cohorts by risk tier, search projects, review milestone logs, and submit evaluation scores and feedback.
- 🔒 **Secure Role-Based Access**: Dedicated student and faculty workflows with password hashing and project data isolation.

---

## 3. Technology Stack

- **Backend**: Python 3.10+, Flask, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, Flask-WTF.
- **Machine Learning**: Scikit-learn, XGBoost, SHAP, Pandas, NumPy, Joblib.
- **Database**: SQLite (default local development) / PostgreSQL (production).
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, FontAwesome, Chart.js.
- **Testing**: Pytest.

---

## 4. Application Architecture & Project Structure

```
ccdt project/
├── app/
│   ├── __init__.py                 # Flask App Factory & extension registration
│   ├── models.py                   # Relational DB models (User, Project, Progress, Prediction, etc.)
│   ├── routes/
│   │   ├── main.py                 # Public landing page & methodology guide
│   │   ├── auth.py                 # Authentication (Login, Register, Profile, Password change)
│   │   ├── student.py              # Student dashboard, project CRUD, progress, predict, What-If
│   │   ├── faculty.py              # Faculty dashboard, cohort filters, review & scoring
│   │   └── api.py                  # JSON REST API endpoints
│   ├── services/
│   │   ├── feature_engineering.py  # Automated metric calculation (completion ratio, delay ratio, schedule pressure)
│   │   ├── ml_service.py           # Model loader, inference engine, SHAP/attribution explainers
│   │   ├── recommendation_engine.py# Actionable guidance rules engine
│   │   └── alert_service.py        # Early warning alert detection
│   ├── ml/
│   │   └── config.py               # Feature sets, column lists, and risk category definitions
│   ├── templates/                  # Responsive Jinja2 templates
│   └── static/                     # CSS, Chart.js integrations, and What-If simulator JS
├── data/
│   └── raw/
│       └── demo_student_projects.csv # Synthetic academic training dataset
├── models/
│   ├── trained_model.pkl           # Best serialized classifier
│   ├── pipeline.pkl                # Preprocessing ColumnTransformer
│   ├── feature_config.json         # Feature names & categorical encodings
│   └── model_metadata.json         # Benchmark metrics and training timestamp
├── scripts/
│   ├── generate_demo_data.py       # Synthetic dataset generator
│   ├── train_model.py              # Model benchmarking & selection pipeline
│   ├── evaluate_model.py           # Model diagnostics & confusion matrix report
│   └── predict.py                  # CLI inference utility
├── tests/                          # Automated Pytest suite (Auth, Projects, ML, API, Recs)
├── requirements.txt
├── .env.example
├── config.py
├── run.py                          # App runner & automatic DB seeder
└── README.md
```

---

## 5. Machine Learning Pipeline & Benchmarking

The training pipeline (`scripts/train_model.py`) trains and compares three candidate architectures:
1. **Logistic Regression** (with StandardScaler & balanced class weights)
2. **Random Forest Classifier** (tuned tree depth & min_samples_split)
3. **XGBoost Classifier** (gradient boosted trees)

### Model Selection Criteria
The best model is selected based on a balanced composite score prioritizing **High-Risk Project Recall** (identifying failing projects early) and **ROC-AUC Score**.

| Model | Accuracy | ROC-AUC | F1-Score (Success) | Recall (At-Risk Projects) |
|---|---|---|---|---|
| **Logistic Regression** | **92.6%** | **0.9837** | **0.9437** | **93.29%** |
| **XGBoost** | 92.4% | 0.9785 | 0.9436 | 87.80% |
| **Random Forest** | 92.0% | 0.9772 | 0.9401 | 89.02% |

---

## 6. Derived Feature Engineering

Students enter only raw milestone values. Derived features are computed automatically with zero-division safeguards:
- **Completion Ratio**: `completed_tasks / max(1, total_tasks)`
- **Delay Ratio**: `delayed_tasks / max(1, total_tasks)`
- **Remaining Work**: `max(0, total_tasks - completed_tasks)`
- **Days Remaining**: `max(0, (deadline - current_date).days)`
- **Schedule Pressure**: `remaining_work / max(1, days_remaining)`
- **Test Coverage Gap**: `max(0, progress_percentage - testing_percentage)`
- **Documentation Gap**: `max(0, progress_percentage - documentation_percentage)`
- **Bug Density**: `bugs / max(1, completed_tasks)`

---

## 7. Dataset & Synthetic Data Notice

> **IMPORTANT DISCLAIMER**:  
> The training dataset (`data/raw/demo_student_projects.csv`) contains **synthetic/simulated academic project data** generated for development, testing, and demonstration purposes. It does not represent actual institutional student records. The system is designed so institutions can seamlessly replace `demo_student_projects.csv` with real historical academic data.

---

## 8. Installation & Quick Start

### Step 1: Clone or Navigate to Directory
```bash
cd "ccdt project"
```

### Step 2: Create and Activate Virtual Environment (Optional but Recommended)
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy the `.env.example` file to `.env`:
```bash
copy .env.example .env
```

### Step 5: (Optional) Re-generate Demo Data & Train Models
```bash
# Generate synthetic dataset
python scripts/generate_demo_data.py

# Train & benchmark ML models
python scripts/train_model.py
```

### Step 6: Start the Web Application
```bash
python run.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 9. Pre-Configured Demo Accounts

When started for the first time, `run.py` automatically initializes SQLite and seeds demo users with pre-loaded projects across different risk tiers:

| Role | Email | Password | Pre-Loaded Projects |
|---|---|---|---|
| **Student** | `student@college.edu` | `password123` | • Smart Attendance System (Low Risk)<br>• Decentralized Medical Records (Critical Risk) |
| **Student 2** | `student2@college.edu` | `password123` | • IoT Soil Health & Smart Irrigation (Moderate Risk) |
| **Faculty** | `faculty@college.edu` | `password123` | Full access to monitor and evaluate all student projects |

---

## 10. Running Automated Tests

Run the complete test suite using Pytest:
```bash
python -m pytest -v
```

All unit, integration, ML inference, and security tests will execute:
- `test_auth.py`: Registration, login, logout, and password hashing.
- `test_projects.py`: Project creation and cross-student data isolation.
- `test_ml_pipeline.py`: Feature engineering edge-cases, model loading, and probability outputs.
- `test_recommendations.py`: Constructive guidance rules engine.
- `test_api.py`: REST API endpoints and What-If simulations without DB mutation.

---

## 11. REST API Reference

All protected endpoints require an authenticated session or Bearer authorization.

- `GET /api/projects`: List projects for current student / faculty.
- `GET /api/projects/<id>`: Retrieve specific project metadata, latest progress, and predictions.
- `GET /api/projects/<id>/history`: Retrieve chronological risk history data points.
- `POST /api/projects/<id>/what-if`: Execute real-time What-If scenario simulation via the ML model.
- `GET /api/model/info`: Returns active model metadata, version, and training status.

---

## 12. Ethical Considerations & AI Transparency

- **Statistical Estimation**: ProjectGuard explicitly states on every view that all predictions represent estimated statistical risks based on historical patterns and do not guarantee academic outcomes.
- **Supportive Tone**: The recommendation engine never utilizes discouraging language (e.g. "your project will fail"). It provides actionable guidance to improve testing, unblock delays, and manage scope.
- **Explainability**: Every prediction highlights the underlying drivers via Explainable AI attributions, ensuring decisions are transparent to students and mentors.
