class VLLMDashboard {
    constructor() {
        this.refreshInterval = 5000;
        this.chartHours = 1;
        this.tokenChart = null;
        this.requestChart = null;
        this.weeklyChart = null;
        this.currentServerId = null;
        this.init();
    }

    async init() {
        await this.loadServers();
        await this.loadConfig();
        this.initCharts();
        this.setupEventListeners();
        this.startAutoRefresh();
        this.updateAll();
        this.updateWeeklyReport();
        this.updateWeeklyChart();
    }

    async loadServers() {
        try {
            const response = await fetch('/api/servers');
            const data = await response.json();
            const select = document.getElementById('serverSelect');

            select.innerHTML = '';
            data.servers.forEach(server => {
                const option = document.createElement('option');
                option.value = server.id;
                option.textContent = `${server.name} (${server.host}:${server.port})`;
                if (server.id === data.current) {
                    option.selected = true;
                    this.currentServerId = server.id;
                }
                select.appendChild(option);
            });

            if (data.servers.length === 0) {
                select.innerHTML = '<option value="">No servers configured</option>';
            }
        } catch (error) {
            console.error('Failed to load servers:', error);
        }
    }

    async switchServer(serverId) {
        if (!serverId || serverId === this.currentServerId) return;

        try {
            const select = document.getElementById('serverSelect');
            select.disabled = true;

            const response = await fetch('/api/servers/switch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ server_id: serverId })
            });

            const data = await response.json();
            if (data.success) {
                this.currentServerId = serverId;
                document.getElementById('serverInfo').textContent = data.server?.base_url || '--';
                this.clearCharts();
                await this.updateAll();
                await this.updateWeeklyReport();
                await this.updateWeeklyChart();
            } else {
                alert('Failed to switch server: ' + (data.error || 'Unknown error'));
                select.value = this.currentServerId;
            }
        } catch (error) {
            console.error('Failed to switch server:', error);
            alert('Failed to switch server');
        } finally {
            document.getElementById('serverSelect').disabled = false;
        }
    }

    clearCharts() {
        if (this.tokenChart) {
            this.tokenChart.data.labels = [];
            this.tokenChart.data.datasets[0].data = [];
            this.tokenChart.data.datasets[1].data = [];
            this.tokenChart.update('none');
        }
        if (this.requestChart) {
            this.requestChart.data.labels = [];
            this.requestChart.data.datasets[0].data = [];
            this.requestChart.update('none');
        }
        if (this.weeklyChart) {
            this.weeklyChart.data.labels = [];
            this.weeklyChart.data.datasets[0].data = [];
            this.weeklyChart.data.datasets[1].data = [];
            this.weeklyChart.update('none');
        }
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            const config = await response.json();
            this.refreshInterval = (config.dashboard?.refresh_interval || 5) * 1000;

            document.getElementById('vllmEndpoint').textContent = config.server?.base_url || '--';
            document.getElementById('pollingInterval').textContent = `${config.monitor?.polling_interval || 5}s`;
            document.getElementById('dataRetention').textContent = `${config.monitor?.history_retention_hours || 24}h`;
            document.getElementById('serverInfo').textContent = config.server?.base_url || '--';
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }

    initCharts() {
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#8b98a5',
                        padding: 16,
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                },
                tooltip: {
                    backgroundColor: '#1a1f26',
                    titleColor: '#e7e9ea',
                    bodyColor: '#8b98a5',
                    borderColor: '#2f3336',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#2f3336',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#6e7681',
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 10
                    }
                },
                y: {
                    grid: {
                        color: '#2f3336',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#6e7681',
                        callback: (value) => this.formatNumber(value)
                    },
                    beginAtZero: true
                }
            }
        };

        const tokenCtx = document.getElementById('tokenChart').getContext('2d');
        this.tokenChart = new Chart(tokenCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Prompt Tokens',
                        data: [],
                        borderColor: '#1d9bf0',
                        backgroundColor: 'rgba(29, 155, 240, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Completion Tokens',
                        data: [],
                        borderColor: '#00ba7c',
                        backgroundColor: 'rgba(0, 186, 124, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }
                ]
            },
            options: chartOptions
        });

        const requestCtx = document.getElementById('requestChart').getContext('2d');
        this.requestChart = new Chart(requestCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Requests',
                        data: [],
                        backgroundColor: 'rgba(255, 122, 0, 0.7)',
                        borderColor: '#ff7a00',
                        borderWidth: 1,
                        borderRadius: 4
                    }
                ]
            },
            options: {
                ...chartOptions,
                plugins: {
                    ...chartOptions.plugins,
                    legend: {
                        display: false
                    }
                }
            }
        });

        // Weekly chart
        const weeklyCtx = document.getElementById('weeklyChart').getContext('2d');
        this.weeklyChart = new Chart(weeklyCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Prompt Tokens',
                        data: [],
                        backgroundColor: 'rgba(29, 155, 240, 0.8)',
                        borderColor: '#1d9bf0',
                        borderWidth: 1,
                        borderRadius: 4
                    },
                    {
                        label: 'Completion Tokens',
                        data: [],
                        backgroundColor: 'rgba(0, 186, 124, 0.8)',
                        borderColor: '#00ba7c',
                        borderWidth: 1,
                        borderRadius: 4
                    }
                ]
            },
            options: {
                ...chartOptions,
                scales: {
                    ...chartOptions.scales,
                    x: {
                        ...chartOptions.scales.x,
                        stacked: false
                    },
                    y: {
                        ...chartOptions.scales.y,
                        stacked: false
                    }
                }
            }
        });
    }

    setupEventListeners() {
        document.querySelectorAll('.time-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.chartHours = parseInt(e.target.dataset.hours);
                this.updateCharts();
            });
        });

        document.getElementById('metricsFilter').addEventListener('input', (e) => {
            this.filterMetrics(e.target.value);
        });

        document.getElementById('serverSelect').addEventListener('change', (e) => {
            this.switchServer(e.target.value);
        });

        document.getElementById('refreshReport').addEventListener('click', () => {
            this.updateWeeklyReport();
            this.updateWeeklyChart();
        });
    }

    startAutoRefresh() {
        setInterval(() => this.updateAll(), this.refreshInterval);
        // Update weekly data less frequently
        setInterval(() => {
            this.updateWeeklyReport();
            this.updateWeeklyChart();
        }, 60000); // Every minute
    }

    async updateAll() {
        await Promise.all([
            this.updateSummary(),
            this.updateCharts(),
            this.updateMetrics()
        ]);
        this.updateLastRefresh();
    }

    async updateWeeklyReport() {
        try {
            const response = await fetch('/api/reports/weekly');
            const data = await response.json();

            if (data.error) {
                document.getElementById('reportContent').innerHTML =
                    '<div class="loading">No server selected</div>';
                return;
            }

            const formatChange = (value) => {
                const sign = value >= 0 ? '+' : '';
                const cls = value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral';
                return `<span class="report-stat-change ${cls}">${sign}${value.toFixed(1)}%</span>`;
            };

            document.getElementById('reportContent').innerHTML = `
                <div class="report-block">
                    <h4>This Week's Usage</h4>
                    <div class="report-stat">
                        <span class="report-stat-label">Total Tokens</span>
                        <span class="report-stat-value">
                            ${this.formatNumber(data.current_week.total_tokens)}
                            ${formatChange(data.change.total_tokens)}
                        </span>
                    </div>
                    <div class="report-stat">
                        <span class="report-stat-label">Prompt Tokens</span>
                        <span class="report-stat-value">
                            ${this.formatNumber(data.current_week.prompt_tokens)}
                            ${formatChange(data.change.prompt_tokens)}
                        </span>
                    </div>
                    <div class="report-stat">
                        <span class="report-stat-label">Completion Tokens</span>
                        <span class="report-stat-value">
                            ${this.formatNumber(data.current_week.completion_tokens)}
                            ${formatChange(data.change.completion_tokens)}
                        </span>
                    </div>
                    <div class="report-stat">
                        <span class="report-stat-label">Total Requests</span>
                        <span class="report-stat-value">
                            ${this.formatNumber(data.current_week.requests)}
                            ${formatChange(data.change.requests)}
                        </span>
                    </div>
                </div>

                <div class="report-block">
                    <h4>Daily Averages</h4>
                    <div class="report-stat">
                        <span class="report-stat-label">Avg. Daily Tokens</span>
                        <span class="report-stat-value">${this.formatNumber(Math.round(data.averages.daily_tokens))}</span>
                    </div>
                    <div class="report-stat">
                        <span class="report-stat-label">Avg. Daily Requests</span>
                        <span class="report-stat-value">${this.formatNumber(Math.round(data.averages.daily_requests))}</span>
                    </div>
                    <div class="report-highlight">
                        <div class="report-highlight-icon peak">📈</div>
                        <div class="report-highlight-content">
                            <div class="report-highlight-label">Peak Day</div>
                            <div class="report-highlight-value">
                                ${data.peak.day || 'N/A'} (${this.formatNumber(data.peak.day_tokens)} tokens)
                            </div>
                        </div>
                    </div>
                    <div class="report-highlight">
                        <div class="report-highlight-icon peak">⏰</div>
                        <div class="report-highlight-content">
                            <div class="report-highlight-label">Peak Hour</div>
                            <div class="report-highlight-value">
                                ${data.peak.hour || 'N/A'} (${this.formatNumber(data.peak.hour_tokens)} tokens)
                            </div>
                        </div>
                    </div>
                </div>

                <div class="report-block">
                    <h4>Previous Week Comparison</h4>
                    <div class="report-stat">
                        <span class="report-stat-label">Last Week Tokens</span>
                        <span class="report-stat-value">${this.formatNumber(data.previous_week.total_tokens)}</span>
                    </div>
                    <div class="report-stat">
                        <span class="report-stat-label">Last Week Requests</span>
                        <span class="report-stat-value">${this.formatNumber(data.previous_week.requests)}</span>
                    </div>
                    <div class="report-stat">
                        <span class="report-stat-label">Token Change</span>
                        <span class="report-stat-value">${formatChange(data.change.total_tokens)}</span>
                    </div>
                    <div class="report-stat">
                        <span class="report-stat-label">Request Change</span>
                        <span class="report-stat-value">${formatChange(data.change.requests)}</span>
                    </div>
                </div>
            `;
        } catch (error) {
            console.error('Failed to update weekly report:', error);
            document.getElementById('reportContent').innerHTML =
                '<div class="loading">Failed to load report</div>';
        }
    }

    async updateWeeklyChart() {
        try {
            const response = await fetch('/api/reports/daily?days=7');
            const data = await response.json();

            if (data.daily && data.daily.length > 0) {
                const labels = data.daily.map(d => {
                    const date = new Date(d.date);
                    return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
                });
                const promptData = data.daily.map(d => d.prompt_tokens);
                const completionData = data.daily.map(d => d.completion_tokens);

                this.weeklyChart.data.labels = labels;
                this.weeklyChart.data.datasets[0].data = promptData;
                this.weeklyChart.data.datasets[1].data = completionData;
                this.weeklyChart.update('none');
            }
        } catch (error) {
            console.error('Failed to update weekly chart:', error);
        }
    }

    async updateSummary() {
        try {
            const response = await fetch('/api/stats/summary');
            const data = await response.json();

            // Update health status
            const statusEl = document.getElementById('connectionStatus');
            const statusDot = statusEl.querySelector('.status-dot');
            const statusText = statusEl.querySelector('.status-text');
            const status = data.health?.status || 'unknown';

            statusDot.className = `status-dot ${status}`;
            statusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);

            const serviceStatus = document.getElementById('serviceStatus');
            serviceStatus.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            serviceStatus.className = `info-value status-badge ${status}`;

            // Update server info
            if (data.server) {
                document.getElementById('serverInfo').textContent = data.server.base_url;
                document.getElementById('vllmEndpoint').textContent = data.server.base_url;
            }

            // Update token stats
            document.getElementById('promptTokens').textContent =
                this.formatNumber(data.tokens?.last_24h?.prompt_tokens || 0);
            document.getElementById('completionTokens').textContent =
                this.formatNumber(data.tokens?.last_24h?.completion_tokens || 0);
            document.getElementById('totalTokens').textContent =
                this.formatNumber(data.tokens?.last_24h?.total_tokens || 0);
            document.getElementById('totalRequests').textContent =
                this.formatNumber(data.tokens?.last_24h?.requests || 0);

            document.getElementById('promptTokensHour').textContent =
                `Last hour: ${this.formatNumber(data.tokens?.last_hour?.prompt_tokens || 0)}`;
            document.getElementById('completionTokensHour').textContent =
                `Last hour: ${this.formatNumber(data.tokens?.last_hour?.completion_tokens || 0)}`;
            document.getElementById('totalTokensHour').textContent =
                `Last hour: ${this.formatNumber(data.tokens?.last_hour?.total_tokens || 0)}`;
            document.getElementById('requestsHour').textContent =
                `Last hour: ${this.formatNumber(data.tokens?.last_hour?.requests || 0)}`;

            // Update system stats
            document.getElementById('runningRequests').textContent =
                data.system?.running_requests ?? '--';
            document.getElementById('pendingRequests').textContent =
                data.system?.pending_requests ?? '--';
            document.getElementById('gpuUtilization').textContent =
                data.system?.gpu_utilization != null
                    ? `${(data.system.gpu_utilization * 100).toFixed(1)}%`
                    : '--';

            // Update models
            const modelsList = document.getElementById('modelsList');
            if (data.models && data.models.length > 0) {
                modelsList.innerHTML = data.models.map(model => `
                    <div class="model-item">
                        <div class="model-icon">M</div>
                        <span class="model-name">${model}</span>
                    </div>
                `).join('');
            } else {
                modelsList.innerHTML = '<div class="loading">No models loaded</div>';
            }

        } catch (error) {
            console.error('Failed to update summary:', error);
        }
    }

    async updateCharts() {
        try {
            const response = await fetch(`/api/metrics/tokens?hours=${this.chartHours}`);
            const data = await response.json();

            if (data.history && data.history.length > 0) {
                const labels = data.history.map(d => this.formatTime(d.timestamp));
                const promptData = data.history.map(d => d.prompt_tokens);
                const completionData = data.history.map(d => d.completion_tokens);
                const requestData = data.history.map(d => d.requests);

                this.tokenChart.data.labels = labels;
                this.tokenChart.data.datasets[0].data = promptData;
                this.tokenChart.data.datasets[1].data = completionData;
                this.tokenChart.update('none');

                this.requestChart.data.labels = labels;
                this.requestChart.data.datasets[0].data = requestData;
                this.requestChart.update('none');
            }
        } catch (error) {
            console.error('Failed to update charts:', error);
        }
    }

    async updateMetrics() {
        try {
            const response = await fetch('/api/metrics/current');
            const data = await response.json();

            const tbody = document.getElementById('metricsTableBody');
            const metrics = data.metrics || {};

            if (Object.keys(metrics).length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" class="loading">No metrics available</td></tr>';
                return;
            }

            const rows = Object.entries(metrics)
                .sort((a, b) => a[0].localeCompare(b[0]))
                .map(([key, data]) => `
                    <tr data-name="${data.name.toLowerCase()}">
                        <td>${data.name}</td>
                        <td>${this.formatMetricValue(data.value)}</td>
                        <td>${data.labels || '-'}</td>
                    </tr>
                `).join('');

            tbody.innerHTML = rows;

            // Re-apply filter if exists
            const filter = document.getElementById('metricsFilter').value;
            if (filter) {
                this.filterMetrics(filter);
            }
        } catch (error) {
            console.error('Failed to update metrics:', error);
        }
    }

    filterMetrics(filter) {
        const rows = document.querySelectorAll('#metricsTableBody tr');
        const filterLower = filter.toLowerCase();

        rows.forEach(row => {
            const name = row.getAttribute('data-name') || '';
            row.style.display = name.includes(filterLower) ? '' : 'none';
        });
    }

    formatNumber(num) {
        if (num >= 1000000000) {
            return (num / 1000000000).toFixed(2) + 'B';
        }
        if (num >= 1000000) {
            return (num / 1000000).toFixed(2) + 'M';
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toLocaleString();
    }

    formatMetricValue(value) {
        if (Number.isInteger(value)) {
            return value.toLocaleString();
        }
        return value.toFixed(4);
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    updateLastRefresh() {
        const now = new Date();
        document.getElementById('lastUpdate').textContent =
            `Last update: ${now.toLocaleTimeString()}`;
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new VLLMDashboard();
});
