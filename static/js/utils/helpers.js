// Utility helper functions
const SpaUtils = {
    // Format timestamp
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    },
    
    // Generate unique ID
    generateId() {
        return Math.random().toString(36).substring(2, 15);
    },
    
    // Show notification
    notify(message, type = 'info') {
        console.log(`[${type.toUpperCase()}] ${message}`);
        // Will be enhanced with actual UI notifications
    }
};