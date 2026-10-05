"""
DEMO / SYNTHETIC DATA GENERATOR FOR PROJEXA
===========================================
IMPORTANT DISCLAIMER:
THIS DATASET CONTAINS SYNTHETIC / SIMULATED ACADEMIC PROJECT DATA GENERATED
FOR DEVELOPMENT, TESTING, AND TRAINING PURPOSES.
IT DOES NOT REPRESENT REAL STUDENT OR INSTITUTIONAL RECORDS.
"""

import os
import random
from pathlib import Path
import numpy as np
import pandas as pd

# Set deterministic seed for reproducibility
np.random.seed(42)
random.seed(42)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = DATA_DIR / "demo_student_projects.csv"

DOMAINS = [
    "Web Development",
    "Mobile Applications",
    "Machine Learning & AI",
    "Internet of Things (IoT)",
    "Cloud Computing",
    "Cybersecurity",
    "Blockchain",
    "Data Science & Analytics"
]

DIFFICULTIES = ["Easy", "Medium", "Hard"]


def generate_synthetic_dataset(num_samples: int = 2000) -> pd.DataFrame:
    """Generates synthetic student project records with realistic academic distributions."""
    records = []

    for i in range(num_samples):
        # Project characteristics
        domain = random.choice(DOMAINS)
        difficulty = random.choices(DIFFICULTIES, weights=[0.25, 0.50, 0.25])[0]
        team_size = random.choices([1, 2, 3, 4, 5], weights=[0.25, 0.40, 0.20, 0.10, 0.05])[0]
        technologies_count = random.randint(1, 6)
        
        # Total tasks typical in academic capstones
        total_tasks = random.randint(10, 45)
        
        # Stage in project lifecycle (from early 10% to final 95%)
        lifecycle_stage = random.uniform(0.15, 0.95)
        
        # Base completion tendency based on difficulty and team size
        base_completion_rate = lifecycle_stage + random.gauss(0, 0.12)
        base_completion_rate = max(0.05, min(1.0, base_completion_rate))
        
        completed_tasks = int(round(total_tasks * base_completion_rate))
        completed_tasks = max(0, min(total_tasks, completed_tasks))
        remaining_tasks = total_tasks - completed_tasks
        
        # Delays
        delay_prop = random.betavariate(1.5, 4.0) if difficulty == "Hard" else random.betavariate(1.2, 5.0)
        delayed_tasks = int(round(remaining_tasks * delay_prop))
        delayed_tasks = max(0, min(remaining_tasks, delayed_tasks))
        pending_tasks = max(0, remaining_tasks - delayed_tasks)
        
        progress_percentage = round((completed_tasks / total_tasks) * 100, 1)
        
        # Testing usually lags behind progress if not disciplined
        testing_lag = random.uniform(5.0, 35.0)
        testing_percentage = max(0.0, round(progress_percentage - testing_lag + random.gauss(0, 5), 1))
        testing_percentage = min(100.0, testing_percentage)
        
        # Documentation
        doc_lag = random.uniform(0.0, 30.0)
        documentation_percentage = max(0.0, round(progress_percentage - doc_lag + random.gauss(0, 5), 1))
        documentation_percentage = min(100.0, documentation_percentage)
        
        # Presentation
        presentation_percentage = max(0.0, min(100.0, round(progress_percentage * random.uniform(0.5, 1.0), 1)))
        
        # Bugs count correlated with tech difficulty and low testing
        bug_factor = (1.5 if difficulty == "Hard" else 1.0) * (1.0 - (testing_percentage / 100.0))
        bugs = int(max(0, round(float(np.random.poisson(lam=max(0.1, 3.5 * bug_factor))))))
        
        # Timeline days remaining
        total_project_days = random.randint(60, 150)
        days_remaining = max(1, int(round(total_project_days * (1.0 - lifecycle_stage))))
        
        # Collaboration & evaluation
        collaboration_rating = round(random.uniform(2.5, 5.0), 1)
        previous_evaluation_score = round(max(35.0, min(98.0, 60.0 + (progress_percentage * 0.3) + random.gauss(0, 8))), 1)
        
        # Derived values
        completion_ratio = round(completed_tasks / total_tasks, 4)
        delay_ratio = round(delayed_tasks / total_tasks, 4)
        remaining_work = total_tasks - completed_tasks
        schedule_pressure = round(remaining_work / max(1, days_remaining), 4)
        test_coverage_gap = max(0.0, round(progress_percentage - testing_percentage, 2))
        doc_coverage_gap = max(0.0, round(progress_percentage - documentation_percentage, 2))
        bug_density = round(bugs / max(1, completed_tasks), 4)

        # Ground truth outcome calculation (1 = Successful, 0 = Failed / Serious At-Risk)
        # Latent score combining critical academic success predictors
        risk_score = (
            - 0.35 * (progress_percentage / 100.0)
            - 0.25 * (testing_percentage / 100.0)
            - 0.15 * (documentation_percentage / 100.0)
            + 0.35 * delay_ratio
            + 0.25 * min(2.0, schedule_pressure)
            + 0.15 * min(3.0, bug_density)
            - 0.10 * (collaboration_rating / 5.0)
            - 0.15 * (previous_evaluation_score / 100.0)
            + (0.12 if difficulty == "Hard" else 0.0)
            + random.gauss(0, 0.08)  # realistic noise
        )
        
        # If risk_score > -0.20 => failure/at-risk (0), else success (1)
        final_result = 0 if risk_score > -0.22 else 1

        record = {
            "project_id_demo": f"DEMO-{i+1:04d}",
            "project_domain": domain,
            "technology_difficulty": difficulty,
            "team_size": team_size,
            "technologies_count": technologies_count,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "delayed_tasks": delayed_tasks,
            "progress_percentage": progress_percentage,
            "testing_percentage": testing_percentage,
            "documentation_percentage": documentation_percentage,
            "presentation_percentage": presentation_percentage,
            "bugs": bugs,
            "days_remaining": days_remaining,
            "collaboration_rating": collaboration_rating,
            "previous_evaluation_score": previous_evaluation_score,
            "completion_ratio": completion_ratio,
            "delay_ratio": delay_ratio,
            "remaining_work": remaining_work,
            "schedule_pressure": schedule_pressure,
            "test_coverage_gap": test_coverage_gap,
            "doc_coverage_gap": doc_coverage_gap,
            "bug_density": bug_density,
            "final_result": final_result
        }
        records.append(record)

    df = pd.DataFrame(records)
    return df


if __name__ == "__main__":
    print("[*] Generating synthetic academic project dataset...")
    df = generate_synthetic_dataset(num_samples=2500)
    
    # Save CSV
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"[+] Successfully generated {len(df)} records.")
    print(f"[+] Saved to: {OUTPUT_FILE}")
    print(f"[+] Class distribution:\n{df['final_result'].value_counts(normalize=True).rename({1: 'Successful (1)', 0: 'At-Risk/Failed (0)'})}")
