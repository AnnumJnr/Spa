/**
 * Game Event Handler
 * Manages WebSocket events and game state updates
 */

class GameEventHandler {
    constructor(gameId, playerId) {
        this.gameId = gameId;
        this.playerId = playerId;  // Keep as string
        
        // Use GAME_CONFIG if available, otherwise build URL
        const config = window.GAME_CONFIG || {};
        this.wsUrl = `${config.wsProtocol || 'ws:'}//${config.wsHost || window.location.host}/ws/game/${gameId}/`;
        if (config.guestName) {
            this.wsUrl += `?guest_name=${encodeURIComponent(config.guestName)}`;
        }
        
        this.socket = null;
        this.board = new GameBoard();
        this.hand = new PlayerHand();
        
        this.gameState = null;
        this.isConnected = false;
        
        // Track played cards for the current round
        this.currentRoundCards = [];
        this.roundComplete = false;
        
        // Setup hand callback
        this.hand.onCardSelected = (card) => this.playCard(card);
        
        this.hideLoading();
    }
    
    /**
     * Connect to WebSocket
     */
    connect() {
        this.showLoading();
        
        console.log('Connecting to WebSocket:', this.wsUrl);
        
        this.socket = new WebSocketManager(this.wsUrl);
        
        // Register event handlers
        this.socket.on('connected', () => this.onConnected());
        this.socket.on('disconnected', () => this.onDisconnected());
        this.socket.on('error', (error) => this.onError(error));
        
        // Game events
        this.socket.on('game_state', (data) => this.onGameState(data));
        this.socket.on('card_played', (data) => this.onCardPlayed(data));
        this.socket.on('your_turn', (data) => this.onYourTurn(data));
        this.socket.on('foul_detected', (data) => this.onFoulDetected(data));
        this.socket.on('set_ended', (data) => this.onSetEnded(data));
        this.socket.on('game_ended', (data) => this.onGameEnded(data));
        this.socket.on('player_connected', (data) => this.onPlayerConnected(data));
        this.socket.on('player_disconnected', (data) => this.onPlayerDisconnected(data));
        this.socket.on('invalid_play', (data) => this.onInvalidPlay(data));
        this.socket.on('lead_changed', (data) => this.onLeadChanged(data));
        this.socket.on('round_started', (data) => this.onRoundStarted(data));
        
        // Connect
        this.socket.connect();
    }
    
    /**
     * Disconnect from WebSocket
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
    
    /**
     * Play a card
     */
    playCard(card) {
        if (!this.isConnected || !card) return;
        
        console.log('Playing card:', card);
        
        this.socket.send({
            action: 'play_card',
            card: {
                suit: card.suit,
                rank: card.rank
            }
        });
        
        // Disable hand while waiting for response
        this.hand.setMyTurn(false);
        
        // Show subtle notification that card was played
        this.board.showNotification('Card played...', 'info', 800);
    }
    
    /**
     * Request current game state
     */
    requestState() {
        if (!this.isConnected) return;
        
        this.socket.send({
            action: 'request_state'
        });
    }
    
    // ========== Event Handlers ==========
    
    onConnected() {
        console.log('Connected to game');
        this.isConnected = true;
        this.hideLoading();
    }
    
    onDisconnected() {
        console.log('Disconnected from game');
        this.isConnected = false;
        this.board.showNotification('Disconnected from server', 'error');
        this.showLoading();
    }
    
    onError(error) {
        console.error('WebSocket error:', error);
        this.board.showNotification('Connection error', 'error');
    }
    
    /**
     * Handle game state update
     */
    onGameState(data) {
        console.log('=== GAME STATE RECEIVED ===');
        console.log('Full game state:', JSON.stringify(data, null, 2));
        
        this.gameState = data;
        
        // Initialize board
        this.board.initialize(data);
        
        // Initialize player's hand
        if (data.hand) {
            console.log('Initializing hand with:', data.hand);
            this.hand.initialize(data.hand);
        }
        
        // Render played cards if any
        if (data.played_cards && data.played_cards.length > 0) {
            this.currentRoundCards = data.played_cards;
            this.board.renderPlayedCards(data.played_cards);
        } else {
            this.currentRoundCards = [];
            this.board.clearPlayedCards();
        }
        
        // Update round info
        if (data.current_round) {
            this.board.updateRoundInfo(data.current_round, data.total_rounds || 5);
        }
        
        // Check if it's player's turn (compare as strings)
        const isMyTurn = data.current_player_id === this.playerId;
        this.hand.setMyTurn(isMyTurn);
        
        // Show turn notification in a non-intrusive way
        if (isMyTurn) {
            this.showTurnNotification();
        }
        
        // Highlight current player
        if (data.current_player_id) {
            this.board.highlightCurrentPlayer(data.current_player_id);
        }
        
        this.hideLoading();
    }
    
    /**
     * Show turn notification without blocking the board
     */
    showTurnNotification() {
        // Remove any existing turn notifications
        const existingNotif = document.getElementById('turn-notification');
        if (existingNotif) {
            existingNotif.remove();
        }
        
        // Create a subtle turn indicator
        const notif = document.createElement('div');
        notif.id = 'turn-notification';
        notif.className = 'turn-notification';
        notif.textContent = 'YOUR TURN';
        notif.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--accent-gold, #ffd700);
            color: var(--bg-dark, #1a2a1a);
            padding: 10px 20px;
            border-radius: 30px;
            font-weight: bold;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        `;
        
        document.body.appendChild(notif);
        
        // Fade in
        setTimeout(() => { notif.style.opacity = '1'; }, 10);
        
        // Fade out after 2 seconds
        setTimeout(() => {
            notif.style.opacity = '0';
            setTimeout(() => notif.remove(), 300);
        }, 2000);
    }
    
    /**
     * Handle card played event
     */
    onCardPlayed(data) {
        console.log('Card played:', data);
        
        const { player_id, card, round_complete } = data;
        
        // If this player played the card, remove it from hand
        if (player_id === this.playerId) {
            this.hand.removeCard(card);
        } else {
            // Update opponent's card count
            const player = this.board.players.find(p => p.id === player_id);
            if (player && player.card_count > 0) {
                player.card_count--;
                this.board.updateOpponentCardCount(player_id, player.card_count);
            }
        }
        
        // Add card to played cards center
        this.currentRoundCards.push({ player_id, card });
        this.board.addPlayedCard(player_id, card);
        
        // DON'T clear cards immediately - keep them visible
        // Cards will be cleared when round_complete is true AND we move to next round
        
        // Show subtle notification for non-player plays
        if (player_id !== this.playerId) {
            const player = this.board.players.find(p => p.id === player_id);
            const playerName = player ? (player.display_name || player.name) : 'Opponent';
            this.board.showNotification(`${playerName} played a card`, 'info', 800);
        }
    }
    
    /**
     * Handle your turn event
     */
    onYourTurn(data) {
        console.log('Your turn:', data);
        
        this.hand.setMyTurn(true);
        this.showTurnNotification();
        this.board.highlightCurrentPlayer(this.playerId);
    }
    
    /**
     * Handle round started event
     */
    onRoundStarted(data) {
        console.log('Round started:', data);
        
        const { round_index, lead_player_id } = data;
        
        // Clear played cards for the new round
        this.currentRoundCards = [];
        this.board.clearPlayedCards();
        
        // Update round info
        this.board.updateRoundInfo(round_index + 1);
        
        // Show round notification
        const roundNotif = document.createElement('div');
        roundNotif.className = 'round-notification';
        roundNotif.textContent = `Round ${round_index + 1} Started`;
        roundNotif.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--accent-green, #4caf50);
            color: white;
            padding: 20px 40px;
            border-radius: 10px;
            font-size: 24px;
            font-weight: bold;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.5s;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        `;
        
        document.body.appendChild(roundNotif);
        
        // Fade in
        setTimeout(() => { roundNotif.style.opacity = '1'; }, 10);
        
        // Fade out after 1.5 seconds
        setTimeout(() => {
            roundNotif.style.opacity = '0';
            setTimeout(() => roundNotif.remove(), 500);
        }, 1500);
        
        // Highlight the lead player
        if (lead_player_id) {
            this.board.highlightCurrentPlayer(lead_player_id);
        }
    }
    
    /**
     * Handle foul detected event
     */
    onFoulDetected(data) {
        console.log('Foul detected:', data);
        
        const { fouling_players, reason, penalties } = data;
        
        // Show foul notification
        const fouledPlayerNames = fouling_players.map(pid => {
            const player = this.board.players.find(p => p.id === pid);
            return player ? (player.display_name || player.name) : 'Unknown';
        }).join(', ');
        
        this.board.showNotification(
            `Foul! ${fouledPlayerNames} - ${reason}`, 
            'error', 
            4000
        );
        
        // Update scores
        if (penalties) {
            this.board.updateScores(penalties);
        }
        
        // Mark fouled players
        fouling_players.forEach(pid => {
            this.board.markPlayerFouled(pid);
        });
    }
    
    /**
     * Handle set ended event
     */
    onSetEnded(data) {
        console.log('Set ended:', data);
        
        const { winner_id, score_awarded, new_scores } = data;
        
        const winner = this.board.players.find(p => p.id === winner_id);
        const winnerName = winner ? (winner.display_name || winner.name) : 'Unknown';
        
        this.board.showNotification(
            `Set Won by ${winnerName}! +${score_awarded} points`, 
            'success', 
            4000
        );
        
        // Update scores
        if (new_scores) {
            this.board.updateScores(new_scores);
        }
        
        // Clear played cards for next set
        this.currentRoundCards = [];
        this.board.clearPlayedCards();
    }
    
    /**
     * Handle game ended event
     */
    onGameEnded(data) {
        console.log('Game ended:', data);
        
        const { winner_id, final_scores } = data;
        
        const winner = this.board.players.find(p => p.id === winner_id);
        const winnerName = winner ? (winner.display_name || winner.name) : 'Unknown';
        
        // Update final scores
        if (final_scores) {
            this.board.updateScores(final_scores);
        }
        
        // Show game over notification
        if (winner_id === this.playerId) {
            this.board.showNotification('🎉 You Won! 🎉', 'success', 6000);
        } else {
            this.board.showNotification(`Game Over! Winner: ${winnerName}`, 'info', 6000);
        }
        
        // Disable hand
        this.hand.setMyTurn(false);
        
        // Redirect to home after delay
        setTimeout(() => {
            window.location.href = '/';
        }, 6000);
    }
    
    /**
     * Handle player connected event
     */
    onPlayerConnected(data) {
        console.log('Player connected:', data);
        
        const { player_id, display_name } = data;
        
        this.board.markPlayerConnected(player_id);
        this.board.showNotification(`${display_name} connected`, 'info', 2000);
    }
    
    /**
     * Handle player disconnected event
     */
    onPlayerDisconnected(data) {
        console.log('Player disconnected:', data);
        
        const { player_id } = data;
        
        this.board.markPlayerDisconnected(player_id);
        
        const player = this.board.players.find(p => p.id === player_id);
        const playerName = player ? (player.display_name || player.name) : 'Player';
        
        this.board.showNotification(`${playerName} disconnected`, 'warning', 3000);
    }
    
    /**
     * Handle invalid play event
     */
    onInvalidPlay(data) {
        console.log('Invalid play:', data);
        
        const { reason } = data;
        
        this.board.showNotification(`Invalid play: ${reason}`, 'error', 3000);
        
        // Re-enable turn
        this.hand.setMyTurn(true);
    }
    
    /**
     * Handle lead changed event
     */
    onLeadChanged(data) {
        console.log('Lead changed:', data);
        
        const { new_lead_player_id } = data;
        
        const newLead = this.board.players.find(p => p.id === new_lead_player_id);
        const leadName = newLead ? (newLead.display_name || newLead.name) : 'Unknown';
        
        this.board.showNotification(`Lead changed to ${leadName}!`, 'warning', 2500);
    }
    
    // ========== UI Helpers ==========
    
    showLoading() {
        const loadingOverlay = document.getElementById('loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.classList.remove('hidden');
        }
    }
    
    hideLoading() {
        const loadingOverlay = document.getElementById('loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.classList.add('hidden');
        }
    }
}

// Export for use in template
window.GameEventHandler = GameEventHandler;