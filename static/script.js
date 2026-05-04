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

// Initialize mock Chart.js logic for Simulator
let simChart;
window.onload = function() {
    const ctx = document.getElementById('simChart').getContext('2d');
    simChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Run 1', 'Run 2', 'Run 3', 'Run 4', 'Run 5', 'Run 6'],
            datasets: [{
                label: 'Contributors',
                data: [30, 40, 45, 60, 75, 80],
                borderColor: '#42692c', /* fern-green */
                backgroundColor: 'rgba(66, 105, 44, 0.2)',
                fill: true,
                tension: 0.4
            },
            {
                label: 'Free-Riders',
                data: [70, 60, 55, 40, 25, 20],
                borderColor: '#767ba8', /* periwinkle */
                backgroundColor: 'rgba(118, 123, 168, 0.2)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top' } },
            scales: { y: { beginAtZero: true, max: 100 } }
        }
    });
};

function runSim() {
    // Generate some random fluctuation based on sliders
    const incentive = document.getElementById('incentive').value;
    const newDataCont = [30, 40, 45, parseInt(incentive), parseInt(incentive)+10, parseInt(incentive)+20];
    const newDataFree = newDataCont.map(val => 100 - val);
    
    simChart.data.datasets[0].data = newDataCont;
    simChart.data.datasets[1].data = newDataFree;
    simChart.update();
}