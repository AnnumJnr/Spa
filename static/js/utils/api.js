/**
 * API Utility Functions
 * Handles all API requests with CSRF token management
 */

class API {
    constructor() {
        this.baseUrl = '/api';
        this.csrfToken = this.getCSRFToken();
    }
    
    /**
     * Get CSRF token from cookie
     */
    getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    /**
     * Make a POST request
     */
    async post(endpoint, data = {}) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify(data)
            });
            
            const responseData = await response.json();
            
            if (!response.ok) {
                throw new Error(responseData.error || responseData.message || 'Request failed');
            }
            
            return responseData;
        } catch (error) {
            console.error('API POST error:', error);
            throw error;
        }
    }
    
    /**
     * Make a GET request
     */
    async get(endpoint) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || data.message || 'Request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API GET error:', error);
            throw error;
        }
    }
    
    /**
     * Make a PUT request
     */
    async put(endpoint, data = {}) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify(data)
            });
            
            const responseData = await response.json();
            
            if (!response.ok) {
                throw new Error(responseData.error || responseData.message || 'Request failed');
            }
            
            return responseData;
        } catch (error) {
            console.error('API PUT error:', error);
            throw error;
        }
    }
    
    /**
     * Make a DELETE request
     */
    async delete(endpoint) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                }
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || data.message || 'Request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API DELETE error:', error);
            throw error;
        }
    }
    
    // Convenience methods for specific endpoints
    
    /**
     * Login
     */
    async login(username, password) {
        return await this.post('/accounts/login/', { username, password });
    }
    
    /**
     * Register
     */
    async register(username, email, password, displayName) {
        return await this.post('/accounts/register/', {
            username,
            email,
            password,
            display_name: displayName
        });
    }
    
    /**
     * Logout
     */
    async logout() {
        return await this.post('/accounts/logout/');
    }
    
    /**
     * Create practice game
     */
    async createPracticeGame(botDifficulty, targetScore) {
        return await this.post('/lobby/practice/', {
            bot_difficulty: botDifficulty,
            target_score: targetScore
        });
    }
    
    /**
     * Create room
     */
    async createRoom(roomName, maxPlayers, targetScore, isPrivate) {
        return await this.post('/lobby/rooms/create/', {
            room_name: roomName,
            max_players: maxPlayers,
            target_score: targetScore,
            is_private: isPrivate
        });
    }
    
    /**
     * Join room
     */
    async joinRoom(roomCode) {
        return await this.post(`/lobby/rooms/${roomCode}/join/`);
    }
    
    /**
     * Quick match
     */
    async quickMatch() {
        return await this.post('/lobby/quick-match/');
    }
}

// Create global API instance
window.api = new API();