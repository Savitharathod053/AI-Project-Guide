"""
EARLY WARNING ALERT SERVICE FOR PROJEXA
=======================================
Monitors changes in project risk between consecutive progress milestones and
triggers early warning alerts when risk increases significantly (e.g. >= 15%).
"""

from app.models import db, EarlyWarningAlert, Prediction


def check_and_create_early_warning(project, current_prediction: Prediction) -> EarlyWarningAlert:
    """
    Checks if current prediction risk jumped significantly compared to the prior prediction.
    If so, creates and persists an EarlyWarningAlert record.
    """
    # Fetch prior prediction (excluding current one)
    prior_prediction = project.predictions.filter(Prediction.id != current_prediction.id).first()
    
    if not prior_prediction:
        return None

    prev_risk = float(prior_prediction.failure_probability)
    curr_risk = float(current_prediction.failure_probability)
    risk_jump = round(curr_risk - prev_risk, 1)

    # Threshold for early warning: 15% increase in failure risk
    if risk_jump >= 15.0:
        # Detect possible drivers
        reasons = []
        if current_prediction.progress:
            prog = current_prediction.progress
            if prog.delayed_tasks > 0:
                reasons.append(f"{prog.delayed_tasks} delayed tasks detected")
            if prog.testing_percentage < 30:
                reasons.append("Testing percentage remains low")
            if prog.bugs > 3:
                reasons.append("Unresolved bugs accumulated")
        
        reasons.append("Deadline is approaching with high remaining task load")
        reasons_text = " • " + "\n • ".join(reasons)

        recommended_action = (
            "Schedule an immediate progress review with your team or faculty mentor. "
            "Scope down optional features and prioritize unblocking delayed core tasks."
        )

        alert = EarlyWarningAlert(
            project_id=project.id,
            prediction_id=current_prediction.id,
            previous_risk=prev_risk,
            current_risk=curr_risk,
            risk_jump=risk_jump,
            message=f"Project failure risk increased by +{risk_jump}% (from {prev_risk}% to {curr_risk}%).",
            possible_reasons=reasons_text,
            recommended_action=recommended_action,
            is_read=False
        )
        db.session.add(alert)
        db.session.commit()
        return alert

    return None
