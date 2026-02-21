/**
 * Player Hand Manager
 * Handles rendering and interaction with player's cards
 */

class PlayerHand {
    constructor() {
        this.handContainer = document.getElementById('player-hand');
        this.playButton = document.getElementById('play-btn');
        
        this.cards = [];
        this.selectedCard = null;
        this.isMyTurn = false;
        this.onCardSelected = null; // Callback when card is selected
        
        this.setupPlayButton();
    }
    
    /**
     * Setup play button event listener
     */
    setupPlayButton() {
        if (!this.playButton) return;
        
        this.playButton.addEventListener('click', () => {
            if (this.selectedCard && this.onCardSelected) {
                this.onCardSelected(this.selectedCard);
            }
        });
    }
    
    /**
     * Initialize hand with cards
     */
    initialize(cards) {
        this.cards = cards || [];
        this.selectedCard = null;
        this.render();
    }
    
    /**
     * Update hand with new cards
     */
    updateCards(cards) {
        this.cards = cards || [];
        this.selectedCard = null;
        this.render();
    }
    
    /**
     * Render the hand
     */
    render() {
        if (!this.handContainer) return;
        
        const cardsHTML = this.cards.map(card => {
            const isSelected = this.selectedCard && 
                               this.selectedCard.suit === card.suit && 
                               this.selectedCard.rank === card.rank;
            
            const selectedClass = isSelected ? 'selected' : '';
            const disabledClass = !this.isMyTurn ? 'disabled' : '';
            
            return this.createCardHTML(card, `${selectedClass} ${disabledClass}`);
        }).join('');
        
        this.handContainer.innerHTML = cardsHTML;
        
        // Attach click listeners
        this.attachCardListeners();
    }
    
    /**
     * Attach click listeners to cards
     */
    attachCardListeners() {
        if (!this.handContainer) return;
        
        const cardElements = this.handContainer.querySelectorAll('.card:not(.disabled)');
        
        cardElements.forEach(cardElement => {
            cardElement.addEventListener('click', () => {
                const suit = cardElement.dataset.suit;
                const rank = cardElement.dataset.rank;
                
                // Parse rank to match backend format
                const parsedRank = isNaN(rank) ? rank : parseInt(rank);
                
                this.selectCard({ suit, rank: parsedRank });
            });
        });
    }
    
    /**
     * Select a card
     */
    selectCard(card) {
        // Toggle selection if clicking same card
        if (this.selectedCard && 
            this.selectedCard.suit === card.suit && 
            this.selectedCard.rank === card.rank) {
            this.selectedCard = null;
        } else {
            this.selectedCard = card;
        }
        
        this.render();
        this.updatePlayButton();
    }
    
    /**
     * Remove a card from hand after playing
     */
    removeCard(card) {
        this.cards = this.cards.filter(c => 
            !(c.suit === card.suit && c.rank === card.rank)
        );
        this.selectedCard = null;
        this.render();
        this.updatePlayButton();
    }
    
    /**
     * Enable/disable turn
     */
    setMyTurn(isMyTurn) {
        this.isMyTurn = isMyTurn;
        this.render();
        this.updatePlayButton();
    }
    
    /**
     * Update play button state
     */
    updatePlayButton() {
        if (!this.playButton) return;
        
        if (this.selectedCard && this.isMyTurn) {
            this.playButton.disabled = false;
            this.playButton.textContent = 'Play Card';
        } else {
            this.playButton.disabled = true;
            if (!this.isMyTurn) {
                this.playButton.textContent = 'Waiting...';
            } else {
                this.playButton.textContent = 'Select a Card';
            }
        }
    }
    
    /**
     * Get selected card
     */
    getSelectedCard() {
        return this.selectedCard;
    }
    
    /**
     * Clear selection
     */
    clearSelection() {
        this.selectedCard = null;
        this.render();
        this.updatePlayButton();
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
     * Get cards of a specific suit
     */
    getCardsOfSuit(suit) {
        return this.cards.filter(card => card.suit === suit);
    }
    
    /**
     * Check if hand has a specific suit
     */
    hasSuit(suit) {
        return this.cards.some(card => card.suit === suit);
    }
    
    /**
     * Get number of cards in hand
     */
    getCardCount() {
        return this.cards.length;
    }
}

// Export for use in events.js
window.PlayerHand = PlayerHand;