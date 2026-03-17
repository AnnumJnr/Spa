/**
 * Game Board Manager
 * Handles rendering of opponents, played cards, scores, and round info
 */
console.log('BOARD.JS LOADED - VERSION WITH FIX');
console.log('Current player ID will be:', this.currentPlayerId);


class GameBoard {
    constructor() {
        this.opponentsContainer = document.getElementById('opponents');
        this.playedCardsContainer = document.getElementById('played-cards');
        this.scoresListContainer = document.getElementById('scores-list');
        this.roundNumberElement = document.getElementById('round-number');
        
        this.players = [];
        this.currentPlayerId = null;
        this.currentLeadId = null;
    }
    
    /**
     * Initialize board with game state
     */
    initialize(gameState) {
        this.players = gameState.players || [];
        this.currentPlayerId = gameState.current_player_id;
        this.currentLeadId = gameState.current_lead_id;
        
        this.renderOpponents();
        this.renderScores();
        this.updateRoundInfo(gameState.current_round || 1);
        
        // Clear played cards initially
        this.clearPlayedCards();
    }
    
    /**
     * Render opponent players
     */
    renderOpponents() {
        if (!this.opponentsContainer) return;
        
        // Get opponents (all players except current user) - FIXED: use this.currentPlayerId
        const opponents = this.players.filter(p => p.id !== this.currentPlayerId);
        
        const opponentsHTML = opponents.map(opponent => {
            const cardCount = opponent.card_count || 0;
            const isConnected = opponent.is_connected !== false;
            const isActive = opponent.is_active !== false;
            
            // Create card back elements
            const cardBacksHTML = Array(cardCount).fill('').map(() => 
                '<div class="card card-back"><div class="card-inner">SPA</div></div>'
            ).join('');
            
            return `
                <div class="opponent-player" data-player-id="${opponent.id}">
                    <div class="opponent-name ${!isConnected ? 'text-muted' : ''}">
                        ${opponent.display_name || opponent.name}
                        ${!isConnected ? ' (Disconnected)' : ''}
                        ${!isActive ? ' (Fouled)' : ''}
                    </div>
                    <div class="opponent-cards">
                        ${cardBacksHTML}
                    </div>
                    <div class="opponent-score">${opponent.score || 0}</div>
                </div>
            `;
        }).join('');
        
        this.opponentsContainer.innerHTML = opponentsHTML;
    }
    
    /**
     * Render scores panel
     */
    renderScores() {
        if (!this.scoresListContainer) return;
        
        const scoresHTML = this.players.map(player => {
            // FIXED: use this.currentPlayerId instead of undefined playerId
            const isCurrentPlayer = player.id === this.currentPlayerId;
            const isActive = player.is_active !== false;
            
            return `
                <div class="score-item ${isCurrentPlayer ? 'current-player' : ''}" data-player-id="${player.id}">
                    <div class="score-name">
                        ${player.display_name || player.name}
                        ${!isActive ? ' 💀' : ''}
                    </div>
                    <div class="score-value">${player.score || 0}</div>
                </div>
            `;
        }).join('');
        
        this.scoresListContainer.innerHTML = scoresHTML;

        if (typeof window.updateMobileScores === 'function') {
            window.updateMobileScores();
        }
    }
    
    /**
     * Update scores for specific players
     */
    updateScores(newScores) {
        // Update players array
        Object.entries(newScores).forEach(([playerId, score]) => {
            // FIXED: Remove parseInt since playerId is already a string
            const player = this.players.find(p => p.id === playerId);
            if (player) {
                player.score = score;
            }
        });
        
        // Re-render scores
        this.renderScores();
        
        // Update opponent scores
        Object.entries(newScores).forEach(([playerId, score]) => {
            const opponentElement = this.opponentsContainer?.querySelector(`[data-player-id="${playerId}"] .opponent-score`);
            if (opponentElement) {
                opponentElement.textContent = score;
            }
        });
    }
    
    /**
     * Update round info display
     */
    updateRoundInfo(roundNumber, totalRounds = 5) {
        if (!this.roundNumberElement) return;
        this.roundNumberElement.textContent = `Round ${roundNumber} of ${totalRounds}`;
    }
    
    /**
     * Render played cards in center
     */
    renderPlayedCards(playedCards) {
        if (!this.playedCardsContainer) return;
        
        const cardsHTML = playedCards.map(cardPlay => {
            const card = cardPlay.card;
            // FIXED: Remove parseInt
            const player = this.players.find(p => p.id === cardPlay.player_id);
            const playerName = player ? (player.display_name || player.name) : 'Unknown';
            
            return `
                <div class="played-card-wrapper">
                    <div class="played-card-label">${playerName}</div>
                    ${this.createCardHTML(card)}
                </div>
            `;
        }).join('');
        
        this.playedCardsContainer.innerHTML = cardsHTML;
    }
    
        /**
         * Add a single played card to the center - REPLACES any existing card from this player
         */
        addPlayedCard(playerId, card) {
            // Remove any existing card from this player
            const existingWrapper = this.playedCardsContainer?.querySelector(
                `[data-player-id="${playerId}"]`
            );
            if (existingWrapper) {
                existingWrapper.remove();
            }
            
            const player = this.players.find(p => p.id === playerId);
            const playerName = player ? (player.display_name || player.name) : 'Unknown';
            
            const cardWrapper = document.createElement('div');
            cardWrapper.className = 'played-card-wrapper';
            cardWrapper.setAttribute('data-player-id', playerId); // Add this for lookup
            cardWrapper.innerHTML = `
                <div class="played-card-label">${playerName}</div>
                ${this.createCardHTML(card)}
            `;
            
            this.playedCardsContainer?.appendChild(cardWrapper);
        }  
          
    /**
     * Clear played cards from center
     */
    clearPlayedCards() {
        if (this.playedCardsContainer) {
            this.playedCardsContainer.innerHTML = '';
        }
    }
    
    /**
     * Update opponent card count
     */
    updateOpponentCardCount(playerId, newCount) {
        const opponentElement = this.opponentsContainer?.querySelector(`[data-player-id="${playerId}"]`);
        if (!opponentElement) return;
        
        const cardsContainer = opponentElement.querySelector('.opponent-cards');
        if (!cardsContainer) return;
        
        const cardBacksHTML = Array(newCount).fill('').map(() => 
            '<div class="card card-back"><div class="card-inner">SPA</div></div>'
        ).join('');
        
        cardsContainer.innerHTML = cardBacksHTML;
    }
    
    /**
     * Create HTML for a single card
     */
    createCardHTML(card, extraClasses = '') {
        const suitSymbol = this.getSuitSymbol(card.suit);
        
        return `
            <div class="card ${extraClasses}" data-suit="${card.suit}" data-rank="${card.rank}">
                <div class="card-inner">
                    <div class="card-rank">${card.rank}</div>
                    <div class="card-suit">${suitSymbol}</div>
                </div>
            </div>
        `;
    }
    
    /**
     * Get suit symbol
     */
    getSuitSymbol(suit) {
        const symbols = {
            'Yet': '♥',      // Hearts
            'Kalo': '♦',     // Diamonds
            'Spa': '♠',      // Spades
            'Crane': '♣'     // Clubs
        };
        return symbols[suit] || suit;
    }
    
    /**
     * Show notification in the dedicated notification area
     */
    showNotification(message, type = 'info', duration = 3000) {
        const notificationsContainer = document.getElementById('game-notifications');
        if (!notificationsContainer) {
            // Fallback to old method if new container doesn't exist
            const oldContainer = document.getElementById('notifications');
            if (oldContainer) {
                const notification = document.createElement('div');
                notification.className = `notification notification-${type}`;
                notification.textContent = message;
                oldContainer.appendChild(notification);
                setTimeout(() => notification.remove(), duration);
            }
            return;
        }
        
        // Clear any existing notification
        notificationsContainer.innerHTML = '';
        
        // Create new notification
        const notification = document.createElement('div');
        notification.className = `game-notification ${type}`;
        notification.textContent = message;
        
        notificationsContainer.appendChild(notification);
        
        // Auto-remove after duration
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, duration);
    }
    
    /**
     * Mark player as disconnected
     */
    markPlayerDisconnected(playerId) {
        const player = this.players.find(p => p.id === playerId);
        if (player) {
            player.is_connected = false;
        }
        this.renderOpponents();
    }
    
    /**
     * Mark player as connected
     */
    markPlayerConnected(playerId) {
        const player = this.players.find(p => p.id === playerId);
        if (player) {
            player.is_connected = true;
        }
        this.renderOpponents();
    }
    
    /**
     * Mark player as fouled
     */
    markPlayerFouled(playerId) {
        const player = this.players.find(p => p.id === playerId);
        if (player) {
            player.is_active = false;
        }
        this.renderOpponents();
        this.renderScores();
    }
    
    /**
     * Highlight current turn player
     */
    highlightCurrentPlayer(playerId) {
        // Remove all existing highlights
        document.querySelectorAll('.opponent-player').forEach(el => {
            el.style.border = 'none';
        });
        
        // Highlight the current player
        const opponentElement = this.opponentsContainer?.querySelector(`[data-player-id="${playerId}"]`);
        if (opponentElement) {
            opponentElement.style.border = '2px solid var(--accent-gold)';
            opponentElement.style.borderRadius = 'var(--radius-md)';
        }
    }
}

// Export for use in events.js
window.GameBoard = GameBoard;