// static/js/game/stack.js

/**
 * Stack Manager
 * Handles stack button, gauge, and card selection UI
 */
class StackManager {
    constructor(hand, gameController) {
        this.hand = hand;  // Reference to PlayerHand instance
        this.gameController = gameController;
        
        // DOM elements
        this.stackContainer = document.getElementById('stack-container');
        this.stackBtn = document.getElementById('stack-btn');
        this.stackGaugeFill = document.getElementById('stack-gauge-fill');
        this.stackSelectionControls = document.getElementById('stack-selection-controls');
        this.stackConfirmBtn = document.getElementById('stack-confirm-btn');
        this.stackCancelBtn = document.getElementById('stack-cancel-btn');
        
        // State
        this.isStackMode = false;
        this.selectedCards = [];  // Cards in stack order
        this.gaugePercentage = 0;
        this.gaugeInterval = null;
        this.canStack = false;
        this.stackUsedByOthers = new Set(); // Players who used stack this set
        
        // Bind methods
        this.handleStackClick = this.handleStackClick.bind(this);
        this.handleConfirmStack = this.handleConfirmStack.bind(this);
        this.handleCancelStack = this.handleCancelStack.bind(this);
        this.handleCardClick = this.handleCardClick.bind(this);
        
        // Add event listeners
        this.stackBtn.addEventListener('click', this.handleStackClick);
        this.stackConfirmBtn.addEventListener('click', this.handleConfirmStack);
        this.stackCancelBtn.addEventListener('click', this.handleCancelStack);
    }
    
    /**
     * Update stack gauge percentage
     */
    updateGauge(percentage) {
        this.gaugePercentage = Math.min(100, Math.max(0, percentage));
        if (this.stackGaugeFill) {
            this.stackGaugeFill.style.width = `${this.gaugePercentage}%`;
            
            // Change color based on percentage
            if (this.gaugePercentage >= 100) {
                this.stackGaugeFill.style.background = '#ffd700'; // Gold when full
                this.canStack = true;
                this.updateStackButton();
            } else {
                this.stackGaugeFill.style.background = '#4caf50'; // Green when filling
                this.canStack = false;
                this.updateStackButton();
            }
        }
    }
    
    /**
     * Start gauge fill animation
     */
    startGaugeFill(durationSeconds = 10) {
        this.stopGaugeFill();
        this.updateGauge(0);
        
        const startTime = Date.now();
        this.gaugeInterval = setInterval(() => {
            const elapsed = (Date.now() - startTime) / 1000;
            const percentage = (elapsed / durationSeconds) * 100;
            
            if (percentage >= 100) {
                this.updateGauge(100);
                this.stopGaugeFill();
            } else {
                this.updateGauge(percentage);
            }
        }, 100); // Update every 100ms for smooth animation
    }
    
    /**
     * Stop gauge fill animation
     */
    stopGaugeFill() {
        if (this.gaugeInterval) {
            clearInterval(this.gaugeInterval);
            this.gaugeInterval = null;
        }
    }
    
    /**
     * Reset gauge to empty
     */
    resetGauge() {
        this.stopGaugeFill();
        this.updateGauge(0);
        this.canStack = false;
        this.updateStackButton();
    }
    
   
    /**
     * Update stack button enabled/disabled state
     */
    updateStackButton() {
        if (!this.stackBtn) {
            console.log('❌ Stack button element not found');
            return;
        }
        
        // Get fresh game state to check eligibility
        const gameState = this.gameController.gameState;
        if (!gameState) {
            console.log('❌ No game state available');
            return;
        }
        
        console.log('\n=== STACK BUTTON DEBUG ===');
        console.log('Game state:', {
            current_player_id: gameState.current_player_id,
            current_lead_id: gameState.current_lead_id,
            myPlayerId: this.gameController.playerId
        });
        
        // Check all conditions
        const isLead = gameState.current_lead_id === this.gameController.playerId;
        const playerHasUsedStack = this.gameController.playerHasUsedStack?.() || false;
        const isMyTurn = gameState.current_player_id === this.gameController.playerId;
        const gaugeFull = this.gaugePercentage >= 100 || this.canStack;
        
        console.log('Conditions:', {
            gaugeFull,
            gaugePercentage: this.gaugePercentage,
            canStack: this.canStack,
            playerHasUsedStack,
            isMyTurn,
            isLead,
            isStackMode: this.isStackMode
        });
        
        // Check if player has used stack from game state
        if (gameState.players) {
            const myPlayer = gameState.players.find(p => p.id === this.gameController.playerId);
            console.log('My player data:', myPlayer);
            if (myPlayer) {
                console.log('has_used_stack from game state:', myPlayer.has_used_stack);
            }
        }
        
        // Button is enabled when ALL conditions are met:
        // 1. Gauge is full
        // 2. Player hasn't used stack this set
        // 3. It's player's turn
        // 4. Not in stack mode already
        
        if (gaugeFull && !playerHasUsedStack && isMyTurn && !this.isStackMode) {
            this.stackBtn.disabled = false;
            this.stackBtn.classList.add('pulse-animation');
            console.log('✅ STACK BUTTON ENABLED');
        } else {
            this.stackBtn.disabled = true;
            this.stackBtn.classList.remove('pulse-animation');
            console.log('❌ STACK BUTTON DISABLED');
            
            // Log why it's disabled
            if (!gaugeFull) console.log('  ↳ Reason: Gauge not full');
            if (playerHasUsedStack) console.log('  ↳ Reason: Already used stack');
            if (!isMyTurn) console.log('  ↳ Reason: Not your turn');
            if (this.isStackMode) console.log('  ↳ Reason: Already in stack mode');
        }
        console.log('=== END DEBUG ===\n');
    }

    /**
     * Handle stack button click - enter stack mode
     */
    handleStackClick() {
        console.log('Stack button clicked, canStack:', this.canStack);
        
        if (!this.canStack) {
            console.log('Cannot stack - gauge not full');
            return;
        }
        
        console.log('Entering stack mode');
        this.isStackMode = true;
        this.selectedCards = [];
        
        // Show stack selection controls
        this.stackSelectionControls.style.display = 'flex';
        this.stackBtn.style.display = 'none';
        
        // Enable card selection mode in hand
        console.log('Enabling stack selection mode in hand');
        this.hand.enableStackSelectionMode(this.handleCardClick.bind(this));
        
        // Show notification
        this.gameController.board.showNotification(
            'Select cards to stack in order. Click selected card to remove.',
            'info',
            4000
        );
    }
    
    /**
     * Handle card click during stack selection
     */
    handleCardClick(cardElement, cardData) {
        console.log('Stack selection - card clicked:', cardData);
        console.log('Current selected cards:', this.selectedCards);
        
        // Parse rank to ensure consistent comparison
        const cardKey = `${cardData.suit}-${cardData.rank}`;
        const index = this.selectedCards.findIndex(c => 
            c.suit === cardData.suit && c.rank.toString() === cardData.rank.toString()
        );
        
        if (index === -1) {
            // Card not selected - add it
            console.log('Adding card to stack');
            this.selectedCards.push(cardData);
            
            // Update visual indicator with order number
            const orderNumber = this.selectedCards.length;
            cardElement.setAttribute('data-stack-order', orderNumber);
            cardElement.classList.add('stack-selected');
            
            // Add order badge
            const badge = document.createElement('div');
            badge.className = 'stack-order-badge';
            badge.textContent = orderNumber;
            cardElement.appendChild(badge);
            
        } else {
            // Card already selected - remove it
            console.log('Removing card from stack');
            this.selectedCards.splice(index, 1);
            
            // Remove visual indicator
            cardElement.removeAttribute('data-stack-order');
            cardElement.classList.remove('stack-selected');
            
            // Remove badge
            const badge = cardElement.querySelector('.stack-order-badge');
            if (badge) badge.remove();
            
            // Reorder remaining cards
            this.reorderStackCards();
        }
        
        console.log('Updated selected cards:', this.selectedCards);
        
        // Enable/disable confirm button based on selection
        this.stackConfirmBtn.disabled = this.selectedCards.length === 0;
    }

    /**
     * Handle stack gauge update event
     */
    onStackGaugeUpdate(data) {
        console.log('📊 Stack gauge update:', data);
        if (this.stackManager) {
            this.stackManager.updateGauge(data.percentage);
        }
    }
    
    /**
     * Reorder stack cards after removal
     */
    reorderStackCards() {
        const handElement = document.getElementById('player-hand');
        if (!handElement) return;
        
        // Update order numbers for all selected cards
        this.selectedCards.forEach((cardData, idx) => {
            const order = idx + 1;
            const cardElements = handElement.querySelectorAll('.card');
            
            for (let element of cardElements) {
                const suit = element.getAttribute('data-suit');
                const rank = element.getAttribute('data-rank');
                
                if (suit === cardData.suit && rank === cardData.rank.toString()) {
                    // Update badge
                    const badge = element.querySelector('.stack-order-badge');
                    if (badge) badge.textContent = order;
                    
                    // Update attribute
                    element.setAttribute('data-stack-order', order);
                    break;
                }
            }
        });
    }
    
    /**
     * Handle confirm stack button
     */
    handleConfirmStack() {
        if (this.selectedCards.length === 0) return;
        
        // The first card will be played immediately
        // The rest will be stacked
        this.gameController.stackCards(this.selectedCards);
        
        // Immediately remove ALL selected cards from hand visually
        this.selectedCards.forEach(card => {
            this.hand.removeCard(card); // This removes from UI
        });
        
        this.exitStackMode();
        this.resetGauge();
    }
    
    /**
     * Handle cancel stack button
     */
    handleCancelStack() {
        this.exitStackMode();
        
        // Show notification
        this.gameController.board.showNotification(
            'Stack cancelled',
            'info',
            1500
        );
    }
    
    /**
     * Exit stack mode and clean up UI
     */
    exitStackMode() {
        this.isStackMode = false;
        this.selectedCards = [];
        
        // Hide stack selection controls
        this.stackSelectionControls.style.display = 'none';
        this.stackBtn.style.display = 'block';
        
        // Disable card selection mode in hand
        this.hand.disableStackSelectionMode();
        
        // Remove all stack indicators from cards
        const handElement = document.getElementById('player-hand');
        if (handElement) {
            const cards = handElement.querySelectorAll('.card');
            cards.forEach(card => {
                card.removeAttribute('data-stack-order');
                card.classList.remove('stack-selected');
                const badge = card.querySelector('.stack-order-badge');
                if (badge) badge.remove();
            });
        }
        
        // Update button state
        this.updateStackButton();
    }
    
    /**
     * Handle stack initiated by someone (broadcast)
     */
    onStackInitiated(data) {
        const { player_id, num_cards_stacked } = data;
        
        // Mark this player as having used stack
        this.stackUsedByOthers.add(player_id);
        
        // Show notification
        if (player_id === this.gameController.playerId) {
            this.gameController.board.showNotification(
                `You stacked ${num_cards_stacked} cards!`,
                'success',
                2000
            );
        } else {
            // Find player name
            const player = this.gameController.board.players.find(p => p.id === player_id);
            const playerName = player ? (player.display_name || player.name) : 'Another player';
            this.gameController.board.showNotification(
                `${playerName} stacked ${num_cards_stacked} cards`,
                'warning',
                2000
            );
        }
        
        // Reset gauge for others
        if (player_id !== this.gameController.playerId) {
            this.resetGauge();
            // Gauge will start refilling from server
        }
    }
    
    /**
     * Handle stack interrupted event
     */
    onStackInterrupted(data) {
        const { interrupting_player_id, stack_owner_id } = data;
        
        // Show notification
        if (stack_owner_id === this.gameController.playerId) {
            this.gameController.board.showNotification(
                'Your stack was interrupted!',
                'error',
                3000
            );
        } else {
            const owner = this.gameController.board.players.find(p => p.id === stack_owner_id);
            const ownerName = owner ? (owner.display_name || owner.name) : 'A player';
            const interrupter = this.gameController.board.players.find(p => p.id === interrupting_player_id);
            const interrupterName = interrupter ? (interrupter.display_name || interrupter.name) : 'Another player';
            
            this.gameController.board.showNotification(
                `${interrupterName} interrupted ${ownerName}'s stack!`,
                'warning',
                3000
            );
        }
    }
    
    /**
     * Show/hide stack container based on game state
     */
    setVisible(visible) {
        if (this.stackContainer) {
            this.stackContainer.style.display = visible ? 'flex' : 'none';
            console.log(`Stack container ${visible ? 'shown' : 'hidden'}`);
        }
    }
}

// Export for use in events.js
window.StackManager = StackManager;