// Hamburger menu toggle
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');
    
    if (hamburger) {
        hamburger.addEventListener('click', function() {
            hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
        });
        
        // Close menu when a link is clicked
        document.querySelectorAll('.nav-links a').forEach(link => {
            link.addEventListener('click', function() {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
            });
        });
    }
});

// Update slider labels dynamically
document.querySelectorAll('input[type="range"]').forEach(slider => {
    slider.addEventListener('input', (e) => {
        const span = document.getElementById(`${e.target.id}-val`);
        span.innerText = e.target.id === 'firms' ? e.target.value : e.target.value + '%';
    });
});

// ── ABM core (mirrors abm_mesa.py logic) ──────────────────────────────────────

function mulberry32(seed) {
    return function () {
        seed = (seed + 0x6D2B79F5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

function boxMuller(rng) {
    return Math.sqrt(-2 * Math.log(rng())) * Math.cos(2 * Math.PI * rng());
}

function erfinv(x) {
    const a = 0.147;
    const sign = x < 0 ? -1 : 1;
    x = Math.abs(x);
    const ln = Math.log(1 - x * x);
    const t = 2 / (Math.PI * a) + ln / 2;
    return sign * Math.sqrt(Math.sqrt(t * t - ln / a) - t);
}

function sigmoid(x) { return 1 / (1 + Math.exp(-x)); }

function runABM({ nAgents, gini, incentive, beta, sensitivity, nSteps, seed }) {
    const rng  = mulberry32(seed !== undefined ? seed : 42);
    const mu   = Math.sqrt(2) * erfinv(2 * Math.max(0.01, Math.min(0.999, gini)) - 1);
    const costs = Array.from({ length: nAgents }, () => mu + boxMuller(rng));

    let commons = 0;
    const history = [0];
    for (let s = 0; s < nSteps; s++) {
        let contrib = 0;
        for (const c of costs) {
            if (rng() < sigmoid((incentive + commons * beta - c) * sensitivity)) contrib++;
        }
        commons = contrib / nAgents;
        history.push(commons * 100);
    }
    return history;
}

function findTippingPoint(gini, nAgents, beta, sensitivity) {
    const N_PTS = 50, N_RUNS = 3, N_STEPS = 25;
    for (let i = 0; i <= N_PTS; i++) {
        const incentive = (i / N_PTS) * 4;
        let total = 0;
        for (let r = 0; r < N_RUNS; r++) {
            const h = runABM({ nAgents, gini, incentive, beta, sensitivity, nSteps: N_STEPS, seed: 42 + r * 100 });
            total += h[h.length - 1];
        }
        if (total / N_RUNS >= 50) return incentive;
    }
    return null;
}

// ── Chart initialisation ───────────────────────────────────────────────────────

let simChart;

document.addEventListener('DOMContentLoaded', function () {
    const canvas = document.getElementById('simChart');
    if (!canvas) return;

    const N_STEPS = 30;
    const labels  = Array.from({ length: N_STEPS + 1 }, (_, i) => i);

    simChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Contributors',
                    data: Array(N_STEPS + 1).fill(null),
                    borderColor: '#42692c',
                    backgroundColor: 'rgba(66, 105, 44, 0.15)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    borderWidth: 2,
                },
                {
                    label: 'Free-Riders',
                    data: Array(N_STEPS + 1).fill(null),
                    borderColor: '#ff6b9d',
                    backgroundColor: 'rgba(255, 107, 157, 0.15)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    borderWidth: 2,
                },
                {
                    label: 'Tipping Point (50%)',
                    data: Array(N_STEPS + 1).fill(50),
                    borderColor: '#b3d462',
                    borderDash: [6, 4],
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    tension: 0,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 600 },
            plugins: { legend: { display: false } },
            scales: {
                x: { title: { display: true, text: 'Simulation Step', color: '#332826' }, ticks: { color: '#332826' }, grid: { color: 'rgba(0,0,0,0.08)' } },
                y: { beginAtZero: true, max: 100, title: { display: true, text: '% of Firms', color: '#332826' }, ticks: { color: '#332826' }, grid: { color: 'rgba(0,0,0,0.08)' } },
            },
        },
    });
});

// ── Run Simulation ─────────────────────────────────────────────────────────────

let animInterval = null;

function runSim() {
    const nAgents      = parseInt(document.getElementById('firms').value);
    const freeRiderPct = parseInt(document.getElementById('freerider').value);
    const costPct      = parseInt(document.getElementById('cost').value);

    const gini        = Math.max(0.01, freeRiderPct / 100);
    const beta        = 3 - 2 * (costPct / 100);
    const sensitivity = 1.5;
    const N_STEPS     = 30;

    // Find tipping point first, then visualise the run at exactly that incentive
    const tip       = findTippingPoint(gini, nAgents, beta, sensitivity);
    const incentive = tip !== null ? tip : 0;

    const history     = runABM({ nAgents, gini, incentive, beta, sensitivity, nSteps: N_STEPS, seed: 42 });
    const freeHistory = history.map(v => 100 - v);

    const resultEl = document.getElementById('tipping-result');
    const barEl    = document.getElementById('tipping-bar');
    if (tip !== null) {
        resultEl.textContent = tip.toFixed(2);
        barEl.style.width    = Math.min(100, (tip / 4) * 100) + '%';
    } else {
        resultEl.textContent = 'N/A';
        barEl.style.width    = '0%';
    }

    // Animate chart tick-by-tick
    if (animInterval) clearInterval(animInterval);
    simChart.data.datasets[0].data = Array(N_STEPS + 1).fill(null);
    simChart.data.datasets[1].data = Array(N_STEPS + 1).fill(null);
    simChart.update('none');

    let step = 0;
    animInterval = setInterval(() => {
        simChart.data.datasets[0].data[step] = history[step];
        simChart.data.datasets[1].data[step] = freeHistory[step];
        simChart.update('none');
        step++;
        if (step >= history.length) {
            clearInterval(animInterval);
            animInterval = null;
        }
    }, 60);
}