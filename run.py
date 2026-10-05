"""
APPLICATION RUNNER & DATABASE SEEDER FOR PROJEXA
=================================================
Initializes SQLite database tables and seeds demo student and faculty
accounts and representative academic projects with AI task breakdowns and ML predictions.
"""

import os
import json
from datetime import date, timedelta
from app import create_app
from app.models import (
    db, User, Project, Task, ProjectProgress, Prediction, Recommendation,
    ProjectCheckin, AIMentorMessage, FacultyFeedback, EarlyWarningAlert,
    ProjectResource, AIRecommendation
)
from app.services.feature_engineering import prepare_feature_row
from app.services.ml_service import get_ml_service
from app.services.ai_service import get_ai_service
from app.services.health_service import calculate_project_health_score
from app.services.recommendation_engine import generate_recommendations

app = create_app(os.environ.get("FLASK_ENV", "development"))


def seed_demo_database():
    """Seeds initial demonstration users, projects with AI tasks, and ML predictions."""
    with app.app_context():
        # Remove old sqlite file if schema has upgraded
        db.create_all()

        # Check if users already exist
        if User.query.first() is not None:
            return

        print("[*] Seeding demo database with Student, Faculty, and AI-mentored academic projects...")

        # 1. Create Faculty User
        faculty = User(
            name="Dr. Sarah Williams",
            email="faculty@college.edu",
            role="faculty",
            department="Computer Science & Engineering"
        )
        faculty.set_password("password123")
        db.session.add(faculty)

        # 2. Create Student 1 (Alex Johnson)
        student1 = User(
            name="Alex Johnson",
            email="student@college.edu",
            role="student",
            department="Computer Science & Engineering"
        )
        student1.set_password("password123")
        db.session.add(student1)

        # 3. Create Student 2 (Priya Sharma)
        student2 = User(
            name="Priya Sharma",
            email="student2@college.edu",
            role="student",
            department="Information Technology"
        )
        student2.set_password("password123")
        db.session.add(student2)

        db.session.commit()

        # 4. Seed Project A: "AI-Based Student Attendance System with Voice Commands" (Low Risk / Healthy)
        proj_a = Project(
            owner_id=student1.id,
            project_name="AI-Based Student Attendance System with Voice Commands",
            description="A web application that allows faculty to record attendance using voice commands and allows students to view attendance records and percentages.",
            objective="Automate classroom roll-call using acoustic speech recognition and real-time database logging.",
            project_summary="A modern Flask & PostgreSQL web system leveraging Whisper speech models to transcribe attendance callouts automatically into student course registries.",
            domain="Machine Learning & AI",
            project_type="Capstone Project",
            team_size=3,
            team_members="Alex Johnson, Mark Taylor, Kevin Vance",
            technologies="Python, Flask, PyTorch, Whisper, PostgreSQL, React",
            technologies_count=6,
            technology_difficulty="Medium",
            start_date=date.today() - timedelta(days=60),
            deadline=date.today() + timedelta(days=35),
            initial_task_count=10,
            health_score=86.0
        )
        db.session.add(proj_a)
        db.session.commit()

        # Tasks for Project A
        tasks_a = [
            ("Database Schema & Attendance Records Tables", "Design student, course, and daily attendance tables in PostgreSQL.", "Database", "Critical", "Completed", True, False),
            ("Faculty & Student Authentication RBAC", "Implement password hashing and session tokens.", "Backend", "High", "Completed", True, False),
            ("Voice Recognition & Acoustic Command Processing", "Integrate OpenAI Whisper speech model for name callout transcription.", "Machine Learning", "Critical", "Completed", True, False),
            ("Attendance Processing Core Engine", "Match transcribed student names with enrolled course rosters.", "Backend", "Critical", "Completed", True, False),
            ("Student Attendance Dashboard UI", "Build interactive calendar and percentage charts for students.", "Frontend", "High", "Completed", True, False),
            ("Faculty Voice Attendance Interface", "Audio recording widget with live confidence feedback.", "Frontend", "High", "Completed", True, False),
            ("Unit & Integration Test Suite", "Write automated tests for speech parser and attendance calculations.", "Testing", "High", "Completed", True, False),
            ("Automated Anti-Spoofing & Input Validation", "Sanitize audio streams and handle background classroom noise.", "Backend", "High", "In Progress", True, False),
            ("Academic Project Report & Architecture Diagrams", "Draft thesis chapters 1-4 with system flowcharts.", "Documentation", "High", "In Progress", True, False),
            ("Final Viva Presentation Slides & Demo Script", "Prepare presentation slides and backup video demo.", "Presentation", "Medium", "Not Started", True, False),
            ("Dark Mode Theme Toggle", "Optional UI customizer.", "UI/UX", "Optional", "Completed", False, True)
        ]
        for t in tasks_a:
            db.session.add(Task(
                project_id=proj_a.id,
                title=t[0],
                description=t[1],
                category=t[2],
                priority=t[3],
                status=t[4],
                is_core=t[5],
                is_optional=t[6],
                source="AI_GENERATED"
            ))
        db.session.commit()

        # 5. Seed Project B: "Decentralized Medical Records Management" (High/Critical Risk)
        proj_b = Project(
            owner_id=student1.id,
            project_name="Decentralized Medical Records Management",
            description="Solidity smart contracts for HIPAA-compliant patient EHR exchange across hospital networks.",
            objective="Ensure tamper-proof cross-institution patient medical record sharing via Ethereum.",
            project_summary="Ethereum smart contract platform storing encrypted patient records on IPFS with decentralized key-sharing.",
            domain="Blockchain",
            project_type="Major Project",
            team_size=2,
            team_members="Alex Johnson, Daniel White",
            technologies="Solidity, Ethereum, IPFS, Web3.js, React",
            technologies_count=5,
            technology_difficulty="Hard",
            start_date=date.today() - timedelta(days=75),
            deadline=date.today() + timedelta(days=10),
            initial_task_count=10,
            health_score=48.0
        )
        db.session.add(proj_b)
        db.session.commit()

        tasks_b = [
            ("Solidity Smart Contract Architecture", "Draft ERC-721 access-token medical contracts.", "Backend", "Critical", "Completed", True, False),
            ("IPFS Encrypted Storage Gateway", "Upload and pin encrypted patient EHR payloads.", "Backend", "Critical", "Blocked", True, False, "IPFS gateway timeout error and CORS connection failure."),
            ("Patient & Doctor Wallet Authentication", "Integrate MetaMask web3 wallet connection.", "Frontend", "High", "Completed", True, False),
            ("Access Delegation & Revocation Module", "Allow patients to grant temporary doctor access.", "Backend", "High", "In Progress", True, False),
            ("Smart Contract Unit Testing with Hardhat", "Write automated tests for gas optimization and vulnerabilities.", "Testing", "High", "Not Started", True, False),
            ("Patient Health History UI Portal", "React frontend displaying verified doctor access logs.", "Frontend", "Medium", "Not Started", True, False),
            ("Project Thesis Documentation", "Write technical project report.", "Documentation", "High", "Not Started", True, False),
            ("Animated 3D Metaverse Dashboard", "Complex three.js interactive hospital room.", "UI/UX", "Optional", "Not Started", False, True)
        ]
        for t in tasks_b:
            blocker = t[7] if len(t) > 7 else None
            db.session.add(Task(
                project_id=proj_b.id,
                title=t[0],
                description=t[1],
                category=t[2],
                priority=t[3],
                status=t[4],
                is_core=t[5],
                is_optional=t[6],
                source="AI_GENERATED",
                blocker_reason=blocker
            ))
        db.session.commit()

        # Generate ML baseline progress snapshots & predictions for both projects
        ml_service = get_ml_service()
        for p in [proj_a, proj_b]:
            tasks = p.tasks.all()
            completed = p.completed_tasks_count
            total = len(tasks)
            prog_pct = p.calculated_progress_pct
            
            prog = ProjectProgress(
                project_id=p.id,
                total_tasks=total,
                completed_tasks=completed,
                pending_tasks=total - completed,
                delayed_tasks=2 if p == proj_b else 0,
                blocked_tasks=p.blocked_tasks_count,
                progress_percentage=prog_pct,
                testing_percentage=80.0 if p == proj_a else 0.0,
                documentation_percentage=60.0 if p == proj_a else 10.0,
                presentation_percentage=50.0 if p == proj_a else 0.0,
                bugs=0 if p == proj_a else 5,
                collaboration_rating=4.5 if p == proj_a else 3.0,
                evaluation_score=85.0 if p == proj_a else 58.0
            )
            db.session.add(prog)
            db.session.commit()

            df_row = prepare_feature_row(p, prog)
            pred_res = ml_service.predict_risk(df_row)
            prediction = Prediction(
                project_id=p.id,
                progress_id=prog.id,
                success_probability=pred_res["success_probability"],
                failure_probability=pred_res["failure_probability"],
                risk_level=pred_res["risk_level"],
                model_version=pred_res["model_version"],
                shap_values=str(pred_res.get("shap_values", [])).replace("'", '"'),
                risk_factors_list=str(pred_res.get("risk_factors", [])).replace("'", '"')
            )
            db.session.add(prediction)
            db.session.commit()

            # Recommendations
            recs = generate_recommendations({"progress_percentage": prog_pct, "testing_percentage": prog.testing_percentage, "documentation_percentage": prog.documentation_percentage, "delayed_tasks": prog.delayed_tasks, "total_tasks": total, "completed_tasks": completed, "days_remaining": 35 if p == proj_a else 10, "bugs": prog.bugs, "collaboration_rating": prog.collaboration_rating, "team_size": p.team_size, "schedule_pressure": 0.2 if p == proj_a else 1.2}, pred_res)
            for r in recs:
                db.session.add(Recommendation(project_id=p.id, prediction_id=prediction.id, risk_factor=r["risk_factor"], recommendation=r["recommendation"], priority=r.get("priority", "High")))
            db.session.commit()

        # Add faculty feedback for Project A
        db.session.add(FacultyFeedback(
            project_id=proj_a.id,
            faculty_id=faculty.id,
            score=88.0,
            feedback="Great progress on the Whisper speech transcription engine. Focus on stress-testing in noisy classroom conditions.",
            milestone_approved=True
        ))

        # Add AI Check-In for Project A
        db.session.add(ProjectCheckin(
            project_id=proj_a.id,
            health_score=86.0,
            risk_level="LOW",
            ai_summary="Your voice recognition and database architecture are progressing ahead of schedule. Automated testing suite is active.",
            recommendations_json=json.dumps([
                "Complete anti-spoofing input validation filters.",
                "Rehearse live viva speech command demo."
            ])
        ))

        # Add AI Mentor message history for Project A
        db.session.add(AIMentorMessage(
            project_id=proj_a.id,
            user_id=student1.id,
            role="user",
            message="Which task should we focus on next before the viva presentation?"
        ))
        db.session.add(AIMentorMessage(
            project_id=proj_a.id,
            user_id=student1.id,
            role="assistant",
            message="You have completed 7 of your 10 core tasks! I recommend finishing the **'Automated Anti-Spoofing & Input Validation'** task next. Having clean error handling will prevent microphone glitching during your live faculty demonstration."
        ))

        db.session.commit()
        print("[+] Demo database seeded successfully with AI Mentor tasks and project states.")


if __name__ == "__main__":
    seed_demo_database()
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] Starting Projexa on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
