/**
 * ProjectGuard Chart.js Utilities
 */

// Initialize Risk History Trend Chart
function initRiskHistoryChart(canvasId, historyData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !historyData || historyData.length === 0) return;

    const labels = historyData.map(d => d.date || d.date_label);
    const failureData = historyData.map(d => d.failure_probability);
    const successData = historyData.map(d => d.success_probability);

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Failure Risk (%)',
                    data: failureData,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 5,
                    pointHoverRadius: 7
                },
                {
                    label: 'Success Probability (%)',
                    data: successData,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.05)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.35,
                    pointRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    ticks: {
                        color: 'rgba(148, 163, 184, 0.85)',
                        callback: function(value) { return value + "%"; }
                    },
                    grid: {
                        color: 'rgba(148, 163, 184, 0.18)'
                    }
                },
                x: {
                    ticks: {
                        color: 'rgba(148, 163, 184, 0.85)'
                    },
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 15
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.y}%`;
                        }
                    }
                }
            }
        }
    });
}

// Initialize Risk Doughnut / Gauge
function initRiskDoughnutChart(canvasId, successProb, failureProb) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Success Probability', 'Failure Risk'],
            datasets: [{
                data: [successProb, failureProb],
                backgroundColor: ['#10b981', '#ef4444'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '72%',
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}
