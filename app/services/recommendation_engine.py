"""
RECOMMENDATION ENGINE FOR PROJECTGUARD
======================================
Derives supportive, actionable, and practical recommendations based on project state,
derived metrics, and ML prediction risk profiles.
"""

from typing import List, Dict


def generate_recommendations(
    project_dict: dict,
    prediction_dict: dict
) -> List[Dict[str, str]]:
    """
    Generates structured, actionable recommendations with priority levels.
    Language is always encouraging and constructive.
    """
    recommendations = []

    progress_pct = float(project_dict.get("progress_percentage", 0.0))
    testing_pct = float(project_dict.get("testing_percentage", 0.0))
    doc_pct = float(project_dict.get("documentation_percentage", 0.0))
    presentation_pct = float(project_dict.get("presentation_percentage", 0.0))
    delayed_tasks = int(project_dict.get("delayed_tasks", 0))
    total_tasks = int(project_dict.get("total_tasks", 10))
    remaining_work = int(project_dict.get("remaining_work", total_tasks - int(project_dict.get("completed_tasks", 0))))
    days_remaining = int(project_dict.get("days_remaining", 30))
    bugs = int(project_dict.get("bugs", 0))
    collab = float(project_dict.get("collaboration_rating", 4.0))
    team_size = int(project_dict.get("team_size", 1))
    failure_prob = float(prediction_dict.get("failure_probability", 20.0))
    schedule_pressure = float(project_dict.get("schedule_pressure", 0.5))

    # 1. Testing gap
    if testing_pct < 30 or (progress_pct - testing_pct > 25):
        recommendations.append({
            "risk_factor": f"Testing Lag (Testing: {testing_pct:.0f}% vs Progress: {progress_pct:.0f}%)",
            "recommendation": "Start testing immediately. Delaying testing makes it harder to discover breaking bugs near the deadline. Implement automated unit and end-to-end tests for core features first.",
            "priority": "Urgent" if testing_pct < 20 else "High"
        })

    # 2. Delayed Tasks
    if delayed_tasks >= 2 or (delayed_tasks / max(1, total_tasks) > 0.15):
        recommendations.append({
            "risk_factor": f"{delayed_tasks} Delayed Milestone Tasks",
            "recommendation": "Prioritize unblocking delayed tasks immediately. Identify root impediments (e.g. dependency versions, API access) and consult your faculty advisor or team peers.",
            "priority": "High"
        })

    # 3. Schedule Pressure & Low Days Remaining
    if days_remaining <= 14 and remaining_work > 3:
        recommendations.append({
            "risk_factor": f"High Schedule Pressure ({remaining_work} tasks with {days_remaining} days left)",
            "recommendation": "Perform Scope Triage: Focus strictly on core deliverables required to demonstrate a functional working prototype. Postpone optional/nice-to-have features to ensure a stable final demo.",
            "priority": "Urgent"
        })

    # 4. Documentation Backlog
    if doc_pct < 30 and progress_pct >= 35:
        recommendations.append({
            "risk_factor": f"Documentation Backlog ({doc_pct:.0f}%)",
            "recommendation": "Begin drafting project documentation, architecture diagrams, and system manuals alongside code development instead of leaving it until the final evaluation week.",
            "priority": "Medium"
        })

    # 5. Bugs Backlog
    if bugs >= 3:
        recommendations.append({
            "risk_factor": f"{bugs} Unresolved Software Bugs",
            "recommendation": "Allocate a dedicated bug-squashing sprint before implementing new features. A stable application with fewer features scores higher than a feature-heavy crash-prone project.",
            "priority": "High" if bugs >= 5 else "Medium"
        })

    # 6. Team Collaboration
    if team_size > 1 and collab <= 3.0:
        recommendations.append({
            "risk_factor": "Team Collaboration Index",
            "recommendation": "Hold a structured team sync to clearly reassign module ownership, review pull requests collaboratively, and balance work distribution.",
            "priority": "Medium"
        })

    # 7. Presentation & Demo Preparation
    if days_remaining <= 10 and presentation_pct < 40:
        recommendations.append({
            "risk_factor": "Final Presentation Preparation",
            "recommendation": "Prepare presentation slides, rehearse your live demonstration, and record a backup video walkthrough in case of network or hardware issues during evaluation.",
            "priority": "High"
        })

    # 8. Positive Maintenance for On-Track Projects
    if failure_prob <= 20.0 and not recommendations:
        recommendations.append({
            "risk_factor": "On-Track Project Health",
            "recommendation": "Your project is progressing smoothly. Continue continuous integration testing, refine UI polish, and prepare documentation for the final viva examination.",
            "priority": "Info"
        })

    # Default reassurance if list is short
    if len(recommendations) == 0:
        recommendations.append({
            "risk_factor": "General Project Guidance",
            "recommendation": "Keep updating task progress periodically and commit code regularly to maintain a consistent milestone velocity.",
            "priority": "Info"
        })

    return recommendations
