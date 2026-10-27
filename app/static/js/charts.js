/**
 * Projexa Chart.js Utilities — Lavender Cloud Theme
 * Palette: Deep Purple (#7C3AED), Soft Lavender (#F0EDFF), Secondary Text (#6B6485), Error Red (#DC2626)
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
                    borderColor: '#DC2626',
                    backgroundColor: 'rgba(220, 38, 38, 0.08)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 5,
                    pointBackgroundColor: '#DC2626',
                    pointHoverRadius: 7
                },
                {
                    label: 'Success Probability (%)',
                    data: successData,
                    borderColor: '#7C3AED',
                    backgroundColor: 'rgba(124, 58, 237, 0.06)',
                    borderWidth: 2.2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: '#7C3AED'
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
                        color: '#6B6485',
                        callback: function(value) { return value + "%"; }
                    },
                    grid: {
                        color: 'rgba(229, 223, 247, 0.8)'
                    }
                },
                x: {
                    ticks: {
                        color: '#6B6485'
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
                        color: '#272044',
                        usePointStyle: true,
                        padding: 15,
                        font: {
                            weight: '600'
                        }
                    }
                },
                tooltip: {
                    backgroundColor: '#FFFFFF',
                    borderColor: '#E5DFF7',
                    borderWidth: 1,
                    titleColor: '#272044',
                    bodyColor: '#272044',
                    padding: 10,
                    boxPadding: 4,
                    displayColors: true,
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
                backgroundColor: ['#7C3AED', '#DC2626'],
                borderColor: '#FFFFFF',
                borderWidth: 3,
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
                },
                tooltip: {
                    backgroundColor: '#FFFFFF',
                    borderColor: '#E5DFF7',
                    borderWidth: 1,
                    titleColor: '#272044',
                    bodyColor: '#272044',
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.parsed}%`;
                        }
                    }
                }
            }
        }
    });
}
