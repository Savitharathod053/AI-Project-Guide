/**
 * ProjectGuard What-If Scenario Simulator Client Logic
 */

document.addEventListener("DOMContentLoaded", function () {
    const whatIfForm = document.getElementById("what-if-form");
    if (!whatIfForm) return;

    const projectId = whatIfForm.dataset.projectId;
    const inputs = whatIfForm.querySelectorAll("input, select");

    // UI elements to update
    const simFailProbEl = document.getElementById("sim-fail-prob");
    const simSuccessProbEl = document.getElementById("sim-success-prob");
    const simRiskBadgeEl = document.getElementById("sim-risk-badge");
    const riskDeltaContainer = document.getElementById("risk-delta-container");
    const riskDeltaText = document.getElementById("risk-delta-text");
    const recsContainer = document.getElementById("sim-recommendations-list");
    const factorsContainer = document.getElementById("sim-factors-list");

    // Sliders with value badges
    const bindSliderBadge = (sliderId, badgeId, suffix = "") => {
        const slider = document.getElementById(sliderId);
        const badge = document.getElementById(badgeId);
        if (slider && badge) {
            slider.addEventListener("input", (e) => {
                badge.innerText = e.target.value + suffix;
            });
        }
    };

    bindSliderBadge("slider-completed-tasks", "badge-completed-tasks");
    bindSliderBadge("slider-delayed-tasks", "badge-delayed-tasks");
    bindSliderBadge("slider-testing", "badge-testing", "%");
    bindSliderBadge("slider-doc", "badge-doc", "%");
    bindSliderBadge("slider-bugs", "badge-bugs");
    bindSliderBadge("slider-days", "badge-days", " days");
    bindSliderBadge("slider-collab", "badge-collab", "/5.0");

    let debounceTimer = null;

    function runSimulation() {
        const payload = {
            total_tasks: parseInt(document.getElementById("slider-total-tasks")?.value || 15),
            completed_tasks: parseInt(document.getElementById("slider-completed-tasks")?.value || 5),
            delayed_tasks: parseInt(document.getElementById("slider-delayed-tasks")?.value || 0),
            testing_percentage: parseFloat(document.getElementById("slider-testing")?.value || 0),
            documentation_percentage: parseFloat(document.getElementById("slider-doc")?.value || 0),
            presentation_percentage: parseFloat(document.getElementById("slider-presentation")?.value || 0),
            bugs: parseInt(document.getElementById("slider-bugs")?.value || 0),
            days_remaining: parseInt(document.getElementById("slider-days")?.value || 30),
            collaboration_rating: parseFloat(document.getElementById("slider-collab")?.value || 4.0),
            technology_difficulty: document.getElementById("select-difficulty")?.value || "Medium"
        };

        // Auto compute progress %
        payload.progress_percentage = Math.round((payload.completed_tasks / Math.max(1, payload.total_tasks)) * 1000) / 10;
        const progressBadge = document.getElementById("badge-calc-progress");
        if (progressBadge) {
            progressBadge.innerText = payload.progress_percentage + "%";
        }

        fetch(`/api/projects/${projectId}/what-if`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                // Update probabilities
                if (simFailProbEl) simFailProbEl.innerText = data.simulated_failure_probability + "%";
                if (simSuccessProbEl) simSuccessProbEl.innerText = data.simulated_success_probability + "%";

                // Update badge
                if (simRiskBadgeEl) {
                    simRiskBadgeEl.className = `badge ${data.simulated_risk_badge} fs-6 px-3 py-2`;
                    simRiskBadgeEl.innerText = data.simulated_risk_level;
                }

                // Update Delta
                if (riskDeltaContainer && riskDeltaText) {
                    const delta = data.risk_improvement;
                    if (delta > 0) {
                        riskDeltaContainer.className = "alert alert-success d-flex align-items-center mb-4";
                        riskDeltaText.innerHTML = `<strong>Great Improvement!</strong> Failure risk decreased by <strong>${delta}%</strong> compared to current baseline.`;
                    } else if (delta < 0) {
                        riskDeltaContainer.className = "alert alert-warning d-flex align-items-center mb-4";
                        riskDeltaText.innerHTML = `<strong>Risk Escalation:</strong> Simulated changes increase failure risk by <strong>${Math.abs(delta)}%</strong>.`;
                    } else {
                        riskDeltaContainer.className = "alert alert-secondary d-flex align-items-center mb-4";
                        riskDeltaText.innerHTML = `No change in failure risk compared to baseline.`;
                    }
                }

                // Update recommendations
                if (recsContainer && data.recommendations) {
                    recsContainer.innerHTML = data.recommendations.map(r => `
                        <li class="list-group-item d-flex align-items-start gap-2 border-0 px-0">
                            <span class="badge ${r.priority === 'Urgent' ? 'bg-danger' : r.priority === 'High' ? 'bg-warning text-dark' : 'bg-primary'} mt-1">${r.priority}</span>
                            <div>
                                <strong class="d-block text-dark">${r.risk_factor}</strong>
                                <span class="text-muted small">${r.recommendation}</span>
                            </div>
                        </li>
                    `).join("");
                }

                // Update risk factors
                if (factorsContainer && data.risk_factors) {
                    factorsContainer.innerHTML = data.risk_factors.map(f => `
                        <div class="${f.direction.includes('Positive') ? 'positive-factor-item' : 'risk-factor-item'}">
                            <i class="fas ${f.direction.includes('Positive') ? 'fa-check-circle text-success' : 'fa-exclamation-circle text-danger'} me-1"></i>
                            <span class="fw-medium">${f.feature_label}</span>
                        </div>
                    `).join("");
                }
            }
        })
        .catch(err => console.error("What-If Simulation Error:", err));
    }

    inputs.forEach(input => {
        input.addEventListener("input", () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(runSimulation, 250);
        });
    });

    // Run initial simulation on load
    runSimulation();
});
