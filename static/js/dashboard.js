// Trading Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard JavaScript loaded');

    // Global variables
    let socket = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;

    // Initialize dashboard
    initializeDashboard();

    function initializeDashboard() {
        console.log('Initializing dashboard...');

        // Setup socket connection
        setupSocketConnection();

        // Setup event listeners
        setupEventListeners();

        // Initial data load
        loadInitialData();
    }

    function setupSocketConnection() {
        try {
            socket = window.socket || io(window.location.origin);

            socket.on('connect', function() {
                console.log('Connected to server');
                updateConnectionStatus(true);
                reconnectAttempts = 0;
        
                // Request data immediately when connected
                socket.emit('request_update');
        
                // Clear any error messages
                clearConnectionErrors();
            });

            socket.on('disconnect', function() {
                console.log('Disconnected from server');
                updateConnectionStatus(false);
                attemptReconnect();
            });

            socket.on('connect_error', function(error) {
                console.error('Connection error:', error);
                updateConnectionStatus(false);
                attemptReconnect();
            });

            socket.on('data_update', function(data) {
                console.log('Received data update');
                handleDataUpdate(data);
            });

            socket.on('reload_page', function(data) {
                console.log('Received reload signal:', data.message);
                showNotification('Dashboard updated, reloading...', 'info');
                setTimeout(function() {
                    window.location.reload();
                }, 1000); // Small delay to show the notification
            });

            socket.on('status', function(data) {
                console.log('Status update:', data.message);
                showNotification(data.message, 'info');
            });

        } catch (error) {
            console.error('Failed to setup socket connection:', error);
            showNotification('Failed to connect to server', 'error');
        }
    }

    function attemptReconnect() {
        if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            console.log(`Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`);

            setTimeout(() => {
                if (!socket.connected) {
                    socket.connect();
                }
            }, 2000 * reconnectAttempts); // Exponential backoff
        } else {
            showNotification('Failed to reconnect to server after multiple attempts', 'error');
        }
    }

    function setupEventListeners() {
        // Handle window resize for responsive charts
        window.addEventListener('resize', function() {
            // Debounce resize events
            clearTimeout(window.resizeTimeout);
            window.resizeTimeout = setTimeout(function() {
                resizeCharts();
            }, 250);
        });

        // Handle visibility change (tab switching)
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden && socket) {
                // Request fresh data when tab becomes visible
                socket.emit('request_update');
            }
        });
    }

    function loadInitialData() {
        // Always show loading state initially
        showLoadingState();

        // Try to emit request after a short delay to allow socket connection
        setTimeout(() => {
            if (socket && socket.connected) {
                socket.emit('request_update');
            } else {
                console.log('Socket not connected, waiting...');
                // Try again after another delay
                setTimeout(() => {
                    if (socket && socket.connected) {
                        socket.emit('request_update');
                    } else {
                        console.log('Socket still not connected, showing error');
                        showConnectionError();
                    }
                }, 2000);
            }
        }, 1000);
    }

    function showConnectionError() {
        const containers = [
            'pnl-overview', 'market-overview', 'active-trades-chart', 'closed-trades-chart',
            'leaderboard-table', 'pnl-comparison-chart', 'sharpe-comparison-chart',
            'performance-overview', 'models-overview', 'agent-details-container'
        ];

        containers.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.innerHTML = `
                    <div class="text-center">
                        <div class="alert alert-danger" role="alert">
                            <i class="fas fa-exclamation-triangle"></i>
                            <strong>Connection Error</strong><br>
                            Unable to connect to the trading dashboard server.<br>
                            Please check if the server is running and accessible.
                        </div>
                    </div>
                `;
            }
        });
    }

    function clearConnectionErrors() {
        const containers = [
            'pnl-overview', 'market-overview', 'active-trades-chart', 'closed-trades-chart',
            'leaderboard-table', 'pnl-comparison-chart', 'sharpe-comparison-chart',
            'performance-overview', 'models-overview', 'agent-details-container'
        ];

        containers.forEach(id => {
            const el = document.getElementById(id);
            if (el && el.innerHTML.includes('alert-danger')) {
                // Clear error and show loading
                el.innerHTML = `
                    <div class="text-center">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <div class="mt-2 text-muted">Loading data...</div>
                    </div>
                `;
            }
        });
    }

    function handleDataUpdate(data) {
        console.log('Processing data update:', data);

        try {
            // Update different sections based on current page
            const currentPage = getCurrentPage();

            switch(currentPage) {
                case 'live':
                    updateLivePage(data);
                    break;
                case 'leaderboard':
                    updateLeaderboardPage(data);
                    break;
                case 'models':
                    updateModelsPage(data);
                    break;
                default:
                    console.warn('Unknown page:', currentPage);
            }

            // Update last update timestamp
            updateLastUpdateTime(data.timestamp);

        } catch (error) {
            console.error('Error processing data update:', error);
            showNotification('Error processing data update', 'error');
        }
    }

    function getCurrentPage() {
        const path = window.location.pathname;
        if (path.includes('/live')) return 'live';
        if (path.includes('/leaderboard')) return 'leaderboard';
        if (path.includes('/models')) return 'models';
        return 'live'; // default
    }

    function updateLivePage(data) {
        // This function will be called from live.html specific script
        if (typeof updateDashboard === 'function') {
            updateDashboard(data);
        }
    }

    function updateLeaderboardPage(data) {
        // This function will be called from leaderboard.html specific script
        if (typeof updateLeaderboard === 'function') {
            updateLeaderboard(data.leaderboard);
        }
        if (typeof updatePNLChart === 'function') {
            updatePNLChart(data.leaderboard);
        }
        if (typeof updateSharpeChart === 'function') {
            updateSharpeChart(data.leaderboard);
        }
        if (typeof updatePerformanceOverview === 'function') {
            updatePerformanceOverview(data.leaderboard);
        }
    }

    function updateModelsPage(data) {
        // This function will be called from models.html specific script
        if (typeof updateModelsOverview === 'function') {
            updateModelsOverview(data.agents);
        }
        if (typeof updateAgentDetails === 'function') {
            updateAgentDetails(data.agents);
        }
    }

    function updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        if (statusEl) {
            if (connected) {
                statusEl.innerHTML = '<i class="fas fa-circle text-success"></i> Connected';
                statusEl.classList.remove('text-danger');
                statusEl.classList.add('text-success');
            } else {
                statusEl.innerHTML = '<i class="fas fa-circle text-danger"></i> Disconnected';
                statusEl.classList.remove('text-success');
                statusEl.classList.add('text-danger');
            }
        }
    }

    function updateLastUpdateTime(timestamp) {
        // Could add a last update indicator if needed
        console.log('Last update:', timestamp);
    }

    function showLoadingState() {
        // Show loading spinners in chart containers
        const containers = [
            'pnl-overview', 'market-overview', 'active-trades-chart', 'closed-trades-chart',
            'leaderboard-table', 'pnl-comparison-chart', 'sharpe-comparison-chart',
            'performance-overview', 'models-overview', 'agent-details-container'
        ];

        containers.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                // Always show loading state initially
                el.innerHTML = `
                    <div class="text-center">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <div class="mt-2 text-muted">Connecting to server...</div>
                    </div>
                `;
            }
        });
    }

    function showNotification(message, type = 'info') {
        // Simple notification system
        console.log(`[${type.toUpperCase()}] ${message}`);

        // Could be enhanced with toast notifications
        // For now, just log to console
    }

    function resizeCharts() {
        // Trigger Plotly resize events
        try {
            const plotlyCharts = document.querySelectorAll('.js-plotly-plot');
            plotlyCharts.forEach(chart => {
                if (window.Plotly) {
                    window.Plotly.Plots.resize(chart);
                }
            });
        } catch (error) {
            console.error('Error resizing charts:', error);
        }
    }

    // Utility functions
    window.formatCurrency = function(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    };

    window.formatPercentage = function(value) {
        return (value * 100).toFixed(2) + '%';
    };

    window.formatNumber = function(value, decimals = 2) {
        return parseFloat(value).toFixed(decimals);
    };

    // Export functions for use in page-specific scripts
    window.DashboardUtils = {
        formatCurrency: window.formatCurrency,
        formatPercentage: window.formatPercentage,
        formatNumber: window.formatNumber,
        showNotification: showNotification
    };
});

// Error handling
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
});