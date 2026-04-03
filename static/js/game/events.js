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
        this.stackManager = new StackManager(this.hand, this);
        
        this.gameState = null;
        this.isConnected = false;
        
        // Track played cards for the current round
        this.currentRoundCards = [];
        this.roundComplete = false;
        
        // Add a flag to track if we're in 1v1 delay mode
        this.isDelayActive = false;
        
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
        
        // STACK EVENTS - ADD THESE LINES
        this.socket.on('stack_initiated', (data) => this.onStackInitiated(data));
        this.socket.on('stack_interrupted', (data) => this.onStackInterrupted(data));
        this.socket.on('stack_gauge_update', (data) => this.onStackGaugeUpdate(data));
        
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
    
    /**
     * Check if current player has used stack this set
     */
    playerHasUsedStack() {
        const player = this.board.players.find(p => p.id === this.playerId);
        return player ? player.has_used_stack : false;
    }
    
    /**
     * Stack cards request
     */
    stackCards(cards) {
        if (!this.isConnected) return;
        
        console.log('Stacking cards:', cards);
        
        this.socket.send({
            action: 'stack',
            cards: cards.map(c => ({
                suit: c.suit,
                rank: c.rank
            }))
        });
        
        this.stackManager.exitStackMode();
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
    console.log('Player ID:', this.playerId);
    console.log('Hand in state:', data.hand);
    
    this.gameState = data;
    
    // Initialize board
    this.board.initialize(data);
    
    // Initialize player's hand
    if (data.hand) {
        console.log('Initializing hand with:', data.hand);
        this.hand.initialize(data.hand);
    }
    
    // Determine if stack should be visible
    const config = window.GAME_CONFIG || {};
    const isStackEnabled = !config.isPractice && !config.isPrivateRoom;
    
    if (this.stackManager) {
        this.stackManager.setVisible(isStackEnabled);
        console.log(`Stack visibility: ${isStackEnabled} (Practice: ${config.isPractice}, PrivateRoom: ${config.isPrivateRoom})`);
    }
    
    // Update stack gauge if present
    if (data.stack) {
        console.log('Active stack:', data.stack);
    }
    
    // CRITICAL FIX: Only update played cards if this is initial load or round transition
    const backendCardCount = (data.played_cards || []).length;
    const frontendCardCount = this.currentRoundCards.length;
    
    // Case 1: Initial load - render cards from state
    if (backendCardCount > 0 && frontendCardCount === 0) {
        console.log('Initial load - rendering cards from state');
        this.currentRoundCards = data.played_cards;
        this.board.clearPlayedCards();
        this.board.renderPlayedCards(data.played_cards);
    }
    // Case 2: Round transition - backend has 0 cards, we have cards
    else if (backendCardCount === 0 && frontendCardCount > 0) {
        console.log('Round transition - clearing cards');
        this.currentRoundCards = [];
        this.board.clearPlayedCards();
    }
    // Case 3: During round - trust card_played events, ignore game_state
    else {
        console.log('During round - keeping cards from card_played events');
        // Don't update - card_played events handle this
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
    
    onCardPlayed(data) {
        console.log('Card played:', data);
        
        const { player_id, card, round_complete } = data;
        
        // Update hand/opponent cards
        if (player_id === this.playerId) {
            this.hand.removeCard(card);
        } else {
            const player = this.board.players.find(p => p.id === player_id);
            if (player && player.card_count > 0) {
                player.card_count--;
                this.board.updateOpponentCardCount(player_id, player.card_count);
            }
        }
        
        // Add card to board (use addPlayedCard which handles duplicates)
        this.board.addPlayedCard(player_id, card);
        
        // Track it
        this.currentRoundCards = this.currentRoundCards.filter(p => p.player_id !== player_id);
        this.currentRoundCards.push({ player_id, card });
        
        // Show notification
        if (player_id !== this.playerId) {
            const player = this.board.players.find(p => p.id === player_id);
            const playerName = player ? (player.display_name || player.name) : 'Opponent';
            this.board.showNotification(`${playerName} played`, 'info', 500);
        }
    }

    /**
     * Handle your turn event
     */
    onYourTurn(data) {
        console.log('Your turn:', data);
        
        // Only enable if it's actually this player's turn
        if (data.player_id !== this.playerId) {
            console.log('Not my turn, ignoring');
            return;
        }
        
        // Don't enable turn if we're in delay mode
        if (this.isDelayActive) {
            console.log('Delay active - deferring turn activation');
            setTimeout(() => {
                if (!this.isDelayActive) {
                    this.hand.setMyTurn(true);
                    this.showTurnNotification();
                    this.board.highlightCurrentPlayer(this.playerId);
                }
            }, 500);
            return;
        }
        
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
        const isTwoPlayerGame = this.board.players.length === 2;
        
        // For 2-player games, we want to keep cards visible longer
        // The clearing will be handled by the delay in onCardPlayed
        if (!isTwoPlayerGame) {
            // For 3-4 player games, clear when new round starts
            this.currentRoundCards = [];
            this.board.clearPlayedCards();
        } else if (!this.isDelayActive) {
            // For 2-player games, only clear if not in delay
            this.currentRoundCards = [];
            this.board.clearPlayedCards();
        }
        
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
    
    onStackInitiated(data) {
        console.log('Stack initiated:', data);
        
        // Show the first card as played
        if (data.first_card) {
            this.onCardPlayed({
                player_id: data.player_id,
                card: data.first_card,
                round_complete: data.round_complete
            });
        }
        
        if (this.stackManager) {
            this.stackManager.onStackInitiated(data);
        }
    }
    
    /**
     * Handle stack interrupted event
     */
    onStackInterrupted(data) {
        console.log('Stack interrupted:', data);
        if (this.stackManager) {
            this.stackManager.onStackInterrupted(data);
        }
    }
    
    /**
     * Handle stack gauge update event
     */
    onStackGaugeUpdate(data) {
        console.log('Stack gauge update:', data);
        if (this.stackManager) {
            this.stackManager.updateGauge(data.percentage);
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
        
        const { winner_id, final_scores, winner_name } = data;
        
        // Update final scores
        if (final_scores) {
            this.board.updateScores(final_scores);
        }
        
        // Disable hand
        this.hand.setMyTurn(false);
        
        // Resolve winner name
        let displayName = winner_name || '';
        if (!displayName) {
            const winner = this.board.players.find(p => String(p.id) === String(winner_id));
            displayName = winner ? (winner.display_name || winner.name) : 'Unknown';
        }
        
        // Show winner announcement on the board
        const gameContainer = document.querySelector('.game-container') || document.querySelector('.table-center') || document.body;
        
        const announcement = document.createElement('div');
        announcement.id = 'game-winner-announcement';
        announcement.innerHTML = `
            <div class="winner-text">${displayName} wins!</div>
            <button class="btn btn-primary winner-btn" onclick="window.location.href='/modes/'">
                Back to Game Modes
            </button>
        `;
        gameContainer.appendChild(announcement);
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
     * Update mobile scores display
     */
    updateMobileScores() {
        const container = document.getElementById('mobile-scores-list');
        if (!container) return;
        
        if (!this.board || !this.board.players) return;
        
        const players = this.board.players;
        const currentPlayerId = this.playerId;
        
        container.innerHTML = players.map(player => `
            <div class="mobile-score-item ${player.id === currentPlayerId ? 'current-player' : ''}">
                <span class="mobile-score-name">${this.escapeHtml(player.display_name || player.name)}</span>
                <span class="mobile-score-value">${player.score || 0}</span>
            </div>
        `).join('');
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>]/g, function(m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
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