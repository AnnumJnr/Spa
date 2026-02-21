/**
 * WebSocket Manager
 */

class WebSocketManager {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.eventHandlers = {};
        this.connectionState = 'disconnected';
        this.reconnectTimeout = null;
    }
    
    connect() {
        if (this.connectionState === 'connecting' || this.connectionState === 'connected') {
            return;
        }
        
        this.connectionState = 'connecting';
        console.log('WebSocket connecting to:', this.url);
        
        try {
            this.socket = new WebSocket(this.url);
            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.attemptReconnect();
        }
    }
    
    setupEventHandlers() {
        this.socket.onopen = () => {
            console.log('WebSocket connected');
            this.connectionState = 'connected';
            this.reconnectAttempts = 0;
            this.trigger('connected');
        };
        
        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.trigger('error', error);
        };
        
        this.socket.onclose = (event) => {
            console.log('WebSocket disconnected:', event.code, event.reason);
            this.connectionState = 'disconnected';
            this.trigger('disconnected');
            
            if (event.code !== 1000) {
                this.attemptReconnect();
            }
        };
    }
    
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
            return true;
        } else {
            console.error('WebSocket not connected. Current state:', this.connectionState);
            return false;
        }
    }
    
    on(eventType, handler) {
        if (!this.eventHandlers[eventType]) {
            this.eventHandlers[eventType] = [];
        }
        this.eventHandlers[eventType].push(handler);
    }
    
    off(eventType, handler) {
        if (this.eventHandlers[eventType]) {
            this.eventHandlers[eventType] = this.eventHandlers[eventType].filter(h => h !== handler);
        }
    }
    
    trigger(eventType, data = null) {
        if (this.eventHandlers[eventType]) {
            this.eventHandlers[eventType].forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in ${eventType} handler:`, error);
                }
            });
        }
    }
    
    handleMessage(data) {
        const eventType = data.type;
        console.log('WebSocket message:', eventType, data);
        this.trigger(eventType, data.data || data);
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.trigger('reconnect_failed');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
        
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        this.reconnectTimeout = setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    disconnect() {
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
        }
        
        if (this.socket) {
            this.socket.close(1000, 'Client disconnect');
            this.socket = null;
        }
        
        this.connectionState = 'disconnected';
    }
}