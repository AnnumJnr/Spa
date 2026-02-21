/**
 * DOM Utility Functions
 */

const DOM = {
    // Create element with classes and attributes
    createElement(tag, classes = [], attributes = {}) {
        const element = document.createElement(tag);
        
        if (classes.length > 0) {
            element.className = classes.join(' ');
        }
        
        Object.keys(attributes).forEach(key => {
            element.setAttribute(key, attributes[key]);
        });
        
        return element;
    },
    
    // Show toast notification
    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        
        const toast = this.createElement('div', ['toast', `toast-${type}`]);
        toast.innerHTML = `
            <div class="toast-message">${message}</div>
        `;
        
        container.appendChild(toast);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },
    
    // Show/hide loading overlay
    showLoading() {
        document.getElementById('loading-overlay').style.display = 'flex';
    },
    
    hideLoading() {
        document.getElementById('loading-overlay').style.display = 'none';
    },
    
    // Create card element
    createCard(card, clickHandler = null) {
        const cardEl = this.createElement('div', ['card'], {
            'data-suit': card.suit,
            'data-rank': card.rank
        });
        
        cardEl.innerHTML = `
            <div class="card-inner">
                <div class="card-rank">${card.rank}</div>
                <div class="card-suit">${this.getSuitSymbol(card.suit)}</div>
            </div>
        `;
        
        if (clickHandler) {
            cardEl.addEventListener('click', () => clickHandler(card, cardEl));
        }
        
        return cardEl;
    },
    
    // Get suit symbol
    getSuitSymbol(suit) {
        const symbols = {
            'Yet': '♥',
            'Kalo': '♦',
            'Spa': '♠',
            'Crane': '♣'
        };
        return symbols[suit] || '?';
    },
    
    // Clear element children
    clearElement(element) {
        while (element.firstChild) {
            element.removeChild(element.firstChild);
        }
    }
};