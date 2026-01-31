/**
 * OTTO Dashboard - Progressive Web App
 *
 * Mobile-first dashboard for OTTO OS cognitive management.
 *
 * Features:
 * - Real-time status updates
 * - Command execution
 * - Offline support
 * - Push notifications
 */

class OTTODashboard {
    constructor() {
        this.apiBase = window.location.origin + '/api/v1';
        this.refreshInterval = 30000; // 30 seconds
        this.isOnline = navigator.onLine;
        this.accessToken = localStorage.getItem('otto_access_token');
        this.deviceId = localStorage.getItem('otto_device_id');

        this.init();
    }

    async init() {
        // Setup event listeners
        this.setupEventListeners();

        // Check connection
        this.updateConnectionStatus();

        // Initial data load
        await this.loadAllData();

        // Start refresh timer
        this.startRefreshTimer();

        // Setup online/offline handlers
        window.addEventListener('online', () => this.handleOnlineChange(true));
        window.addEventListener('offline', () => this.handleOnlineChange(false));
    }

    setupEventListeners() {
        // Command buttons
        document.querySelectorAll('.command-btn[data-command]').forEach(btn => {
            btn.addEventListener('click', () => this.executeCommand(btn.dataset.command));
        });

        // Refresh button
        document.getElementById('refreshBtn')?.addEventListener('click', () => this.refresh());

        // Navigation
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchView(btn.dataset.view));
        });
    }

    // ==========================================================================
    // API Methods
    // ==========================================================================

    async fetchAPI(endpoint, options = {}) {
        const url = `${this.apiBase}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (this.accessToken) {
            headers['Authorization'] = `Bearer ${this.accessToken}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers,
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    async loadAllData() {
        try {
            await Promise.all([
                this.loadHealth(),
                this.loadState(),
                this.loadSecurityPosture(),
                this.loadCryptoCapabilities(),
                this.loadProjects(),
            ]);
            this.setConnectionStatus('connected');
        } catch (error) {
            console.error('Failed to load data:', error);
            this.setConnectionStatus('error');
        }
    }

    async loadHealth() {
        try {
            const result = await this.fetchAPI('/mobile/sync');

            // Update cognitive state
            const state = result.cognitive_state || {};
            this.updateElement('activeMode', state.active_mode || '--');
            this.updateElement('activeParadigm', state.active_paradigm || '--');
            this.updateElement('currentAltitude', state.current_altitude || '--');

            // Update energy
            const energy = state.energy_level || 'medium';
            this.updateElement('energyLevel', this.formatValue(energy));
            this.updateElement('energyDetail', this.getEnergyDetail(energy));
            this.setCardStatus('energyCard', this.getEnergyStatus(energy));

            // Update burnout
            const burnout = state.burnout_level || 'GREEN';
            this.updateElement('burnoutLevel', burnout);
            this.updateElement('burnoutDetail', this.getBurnoutDetail(burnout));
            this.setCardStatus('burnoutCard', this.getBurnoutStatus(burnout));

            // Update momentum
            const momentum = state.momentum_phase || 'building';
            this.updateElement('momentumPhase', this.formatValue(momentum));
            this.updateElement('momentumDetail', this.getMomentumDetail(momentum));

            // Update health status
            this.updateElement('healthStatus', 'OK');
            this.updateElement('healthDetail', 'All systems operational');
            this.setCardStatus('healthCard', 'healthy');

        } catch (error) {
            this.updateElement('healthStatus', 'Error');
            this.updateElement('healthDetail', 'Connection failed');
            this.setCardStatus('healthCard', 'critical');
        }
    }

    async loadState() {
        try {
            const result = await this.executeCommand('state', {}, false);
            if (result?.success && result?.result) {
                const state = result.result;
                this.updateElement('activeMode', state.active_mode || '--');
            }
        } catch (error) {
            console.warn('Failed to load state:', error);
        }
    }

    async loadSecurityPosture() {
        try {
            const result = await this.fetchAPI('/security/posture');

            const score = result.score || 0;
            const grade = result.grade || '--';

            // Update score circle
            const scoreCircle = document.getElementById('securityScore');
            if (scoreCircle) {
                scoreCircle.style.setProperty('--score-percent', `${score}%`);
                const scoreValue = scoreCircle.querySelector('.score-value');
                if (scoreValue) {
                    scoreValue.textContent = score;
                }
            }

            // Update grade
            const gradeEl = document.getElementById('securityGrade');
            if (gradeEl) {
                gradeEl.textContent = grade;
                gradeEl.className = `item-value grade grade-${grade.toLowerCase()}`;
            }

        } catch (error) {
            console.warn('Failed to load security posture:', error);
            this.updateElement('securityGrade', '--');
        }
    }

    async loadCryptoCapabilities() {
        try {
            const result = await this.fetchAPI('/security/crypto');

            // PQ Status
            const pqAvailable = result.post_quantum?.available || false;
            this.updateElement('pqStatus', pqAvailable ? 'Active' : 'Disabled');

            // E2E Status
            const e2eEnabled = result.e2e?.enabled || false;
            this.updateElement('e2eStatus', e2eEnabled ? 'Enabled' : 'Disabled');

        } catch (error) {
            console.warn('Failed to load crypto capabilities:', error);
            this.updateElement('pqStatus', '--');
            this.updateElement('e2eStatus', '--');
        }
    }

    async loadProjects() {
        try {
            const result = await this.executeCommand('projects', {}, false);

            const projectsList = document.getElementById('projectsList');
            if (!projectsList) return;

            // Clear existing content safely
            while (projectsList.firstChild) {
                projectsList.removeChild(projectsList.firstChild);
            }

            if (result?.success && result?.result?.projects) {
                const projects = result.result.projects;

                if (projects.length === 0) {
                    const emptyItem = this.createProjectItem(null, 'No active projects', true);
                    projectsList.appendChild(emptyItem);
                    return;
                }

                projects.forEach(project => {
                    const item = this.createProjectItem(project);
                    projectsList.appendChild(item);
                });
            } else {
                const errorItem = this.createProjectItem(null, 'Failed to load projects', true);
                projectsList.appendChild(errorItem);
            }

        } catch (error) {
            console.warn('Failed to load projects:', error);
        }
    }

    /**
     * Create a project item element safely (no innerHTML)
     */
    createProjectItem(project, message = null, isLoading = false) {
        const item = document.createElement('div');
        item.className = 'project-item';

        if (isLoading || !project) {
            item.classList.add('loading');
            item.textContent = message || 'Loading...';
            return item;
        }

        // Add status class
        const status = project.status?.toLowerCase() || '';
        if (status) {
            item.classList.add(status);
        }

        // Create info container
        const info = document.createElement('div');
        info.className = 'project-info';

        const name = document.createElement('span');
        name.className = 'project-name';
        name.textContent = project.slug || project.name || 'Unknown';
        info.appendChild(name);

        const statusText = document.createElement('span');
        statusText.className = 'project-status';
        statusText.textContent = `Last touched: ${this.formatTimeAgo(project.last_touch)}`;
        info.appendChild(statusText);

        item.appendChild(info);

        // Create badge
        const badge = document.createElement('span');
        badge.className = 'project-badge';
        badge.textContent = project.status || 'ACTIVE';
        item.appendChild(badge);

        return item;
    }

    // ==========================================================================
    // Command Execution
    // ==========================================================================

    async executeCommand(command, args = {}, showOutput = true) {
        const btn = document.querySelector(`.command-btn[data-command="${command}"]`);

        try {
            // Show loading state
            if (btn) {
                btn.classList.add('loading');
            }

            const result = await this.fetchAPI(`/commands/${command}`, {
                method: 'POST',
                body: JSON.stringify(args),
            });

            if (showOutput) {
                this.showOutput(command, result);
            }

            if (result?.success) {
                this.showToast(`Command '${command}' executed`, 'success');
            } else {
                this.showToast(result?.error || 'Command failed', 'error');
            }

            return result;

        } catch (error) {
            if (showOutput) {
                this.showOutput(command, { error: error.message });
            }
            this.showToast(`Failed to execute '${command}'`, 'error');
            throw error;

        } finally {
            if (btn) {
                btn.classList.remove('loading');
            }
        }
    }

    showOutput(command, result) {
        const section = document.getElementById('outputSection');
        const content = document.getElementById('outputContent');

        if (!section || !content) return;

        section.style.display = 'block';
        // Use textContent for safe output
        content.textContent = JSON.stringify(result, null, 2);
    }

    // ==========================================================================
    // UI Helpers
    // ==========================================================================

    updateElement(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
        }
    }

    setCardStatus(cardId, status) {
        const card = document.getElementById(cardId);
        if (card) {
            card.className = `status-card ${status}`;
        }
    }

    formatValue(value) {
        if (!value) return '--';
        return value.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    formatTimeAgo(timestamp) {
        if (!timestamp) return 'Unknown';

        const now = Date.now() / 1000;
        const diff = now - timestamp;

        if (diff < 60) return 'Just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    }

    getEnergyDetail(energy) {
        const details = {
            high: 'Peak performance',
            medium: 'Steady state',
            low: 'Needs break',
            depleted: 'Rest required',
        };
        return details[energy] || 'Unknown';
    }

    getEnergyStatus(energy) {
        const statuses = {
            high: 'healthy',
            medium: 'healthy',
            low: 'warning',
            depleted: 'critical',
        };
        return statuses[energy] || 'healthy';
    }

    getBurnoutDetail(burnout) {
        const details = {
            GREEN: 'Safe zone',
            YELLOW: 'Take a break soon',
            ORANGE: 'Check in needed',
            RED: 'Stop and rest',
        };
        return details[burnout] || 'Unknown';
    }

    getBurnoutStatus(burnout) {
        const statuses = {
            GREEN: 'healthy',
            YELLOW: 'warning',
            ORANGE: 'warning',
            RED: 'critical',
        };
        return statuses[burnout] || 'healthy';
    }

    getMomentumDetail(momentum) {
        const details = {
            cold_start: 'Warming up',
            building: 'Gaining speed',
            rolling: 'In the flow',
            peak: 'Maximum output',
            crashed: 'Recovery needed',
        };
        return details[momentum] || 'Unknown';
    }

    // ==========================================================================
    // Connection & Refresh
    // ==========================================================================

    updateConnectionStatus() {
        this.isOnline = navigator.onLine;
        this.setConnectionStatus(this.isOnline ? 'connecting' : 'error');
    }

    setConnectionStatus(status) {
        const statusEl = document.getElementById('connectionStatus');
        if (!statusEl) return;

        const dot = statusEl.querySelector('.status-dot');
        const text = statusEl.querySelector('.status-text');

        dot.className = 'status-dot';
        if (status === 'connected') {
            dot.classList.add('connected');
            text.textContent = 'Connected';
        } else if (status === 'error') {
            dot.classList.add('error');
            text.textContent = 'Offline';
        } else {
            text.textContent = 'Connecting...';
        }
    }

    handleOnlineChange(isOnline) {
        this.isOnline = isOnline;
        if (isOnline) {
            this.showToast('Back online', 'success');
            this.refresh();
        } else {
            this.showToast('You are offline', 'warning');
            this.setConnectionStatus('error');
        }
    }

    async refresh() {
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.classList.add('loading');
        }

        try {
            await this.loadAllData();
            this.showToast('Refreshed', 'success');
        } catch (error) {
            this.showToast('Refresh failed', 'error');
        } finally {
            if (refreshBtn) {
                refreshBtn.classList.remove('loading');
            }
        }
    }

    startRefreshTimer() {
        setInterval(() => {
            if (this.isOnline) {
                this.loadAllData().catch(console.error);
            }
        }, this.refreshInterval);
    }

    // ==========================================================================
    // Navigation
    // ==========================================================================

    switchView(view) {
        // Update nav buttons
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });

        // For now, all views are on the same page
        // Future: implement actual view switching
        this.showToast(`Switched to ${view}`, 'success');
    }

    // ==========================================================================
    // Toast Notifications
    // ==========================================================================

    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        container.appendChild(toast);

        // Auto-remove after 3 seconds
        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease-out reverse';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.ottoDashboard = new OTTODashboard();
});
