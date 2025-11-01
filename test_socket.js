const io = require('socket.io-client');

// Test Socket.IO connection to the Flask dashboard
console.log('Testing Socket.IO connection to Flask dashboard...');

const socket = io('http://127.0.0.1:5000', {
    transports: ['websocket', 'polling']
});

socket.on('connect', () => {
    console.log('✅ Connected to server!');
    console.log('Socket ID:', socket.id);

    // Request data update
    console.log('📤 Requesting data update...');
    socket.emit('request_update');
});

socket.on('disconnect', (reason) => {
    console.log('❌ Disconnected from server:', reason);
});

socket.on('connect_error', (error) => {
    console.log('❌ Connection error:', error.message);
});

socket.on('data_update', (data) => {
    console.log('📥 Received data update!');
    console.log('Data keys:', Object.keys(data));

    if (data.agents) {
        console.log(`🤖 Agents: ${data.agents.length}`);
        data.agents.forEach((agent, index) => {
            console.log(`  ${index + 1}. ${agent.kind}: PNL $${agent.pnl?.toFixed(2)}, Sharpe ${agent.summary?.sharpe_ratio?.toFixed(4)}`);
        });
    }

    if (data.leaderboard) {
        console.log(`🏆 Leaderboard: ${data.leaderboard.length} entries`);
        data.leaderboard.slice(0, 3).forEach((entry, index) => {
            console.log(`  ${entry.rank}. ${entry.agent}: $${entry.pnl?.toFixed(2)} (${entry.pnl_percentage?.toFixed(2)}%)`);
        });
    }

    if (data.market) {
        console.log(`📊 Market data: ${Object.keys(data.market).length} coins`);
    }

    console.log('✅ Test completed successfully!');
    socket.disconnect();
});

socket.on('status', (data) => {
    console.log('📢 Status message:', data.message);
});

// Timeout after 10 seconds
setTimeout(() => {
    console.log('⏰ Timeout reached, disconnecting...');
    socket.disconnect();
}, 10000);