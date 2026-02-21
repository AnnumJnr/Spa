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
        
        console.log('=== PLAYING CARD ===');
        console.log('Card to play:', card);
        console.log('Game state before play:', this.gameState);
        console.log('Is connected:', this.isConnected);
        console.log('Game ID:', this.gameId);
        console.log('Player ID:', this.playerId);
        console.log('==================');
        
        this.socket.send({
            action: 'play_card',
            card: {
                suit: card.suit,
                rank: card.rank
            }
        });
        
        // Disable hand while waiting for response
        this.hand.setMyTurn(false);
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
    console.log('Players:', data.players);
    console.log('Hand:', data.hand);
    console.log('Current player ID:', data.current_player_id);
    console.log('My player ID:', this.playerId);
    console.log('Is my turn?', data.current_player_id === this.playerId);
    console.log('===========================');
    
    this.gameState = data;
    
    // Initialize board
    this.board.initialize(data);
    
    // Initialize player's hand
    if (data.hand) {
        console.log('Initializing hand with:', data.hand);
        this.hand.initialize(data.hand);
    } else {
        console.warn('No hand data in game state');
    }
    
    // Render played cards if any
    if (data.played_cards && data.played_cards.length > 0) {
        this.board.renderPlayedCards(data.played_cards);
    }
    
    // Update round info
    if (data.current_round) {
        this.board.updateRoundInfo(data.current_round);
    }
    
    // Check if it's player's turn (compare as strings)
    const isMyTurn = data.current_player_id === this.playerId;
    this.hand.setMyTurn(isMyTurn);
    
    if (isMyTurn) {
        this.board.showNotification('Your Turn!', 'info', 2000);
    }
    
    // Highlight current player
    if (data.current_player_id) {
        this.board.highlightCurrentPlayer(data.current_player_id);
    }
    
    this.hideLoading();
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
            this.board.showNotification('Card played!', 'success', 1500);
        } else {
            // Update opponent's card count
            const player = this.board.players.find(p => p.id === player_id);
            if (player && player.card_count > 0) {
                player.card_count--;
                this.board.updateOpponentCardCount(player_id, player.card_count);
            }
        }
        
        // Add card to played cards center
        this.board.addPlayedCard(player_id, card);
        
        // If round is complete, clear played cards after delay
        if (round_complete) {
            setTimeout(() => {
                this.board.clearPlayedCards();
            }, 2000);
        }
    }
    
    /**
     * Handle your turn event
     */
    onYourTurn(data) {
        console.log('Your turn:', data);
        
        this.hand.setMyTurn(true);
        this.board.showNotification('Your Turn!', 'info', 2000);
        this.board.highlightCurrentPlayer(this.playerId);
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
        
        // Clear played cards
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
    
    /**
     * Handle round started event
     */
    onRoundStarted(data) {
        console.log('Round started:', data);
        
        const { round_index } = data;
        
        this.board.updateRoundInfo(round_index + 1);
        this.board.clearPlayedCards();
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