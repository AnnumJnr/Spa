/**
 * Practice Mode Setup
 */

// Generate bot difficulty selectors based on number of bots
function generateBotSelectors(numBots) {
    const container = document.getElementById('bot-difficulty-selectors');
    container.innerHTML = '';
    
    for (let i = 1; i <= numBots; i++) {
        const botSelector = document.createElement('div');
        botSelector.className = 'bot-selector';
        botSelector.innerHTML = `
            <label for="bot-${i}-difficulty" class="bot-selector-label">
                Bot ${i} Difficulty
            </label>
            <select id="bot-${i}-difficulty" name="bot_${i}_difficulty" class="form-select">
                <option value="beginner">Beginner (Easy)</option>
                <option value="intermediate" selected>Intermediate (Normal)</option>
                <option value="advanced">Advanced (Hard)</option>
                <option value="expert">Expert (Very Hard)</option>
            </select>
        `;
        container.appendChild(botSelector);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const numBotsSelect = document.getElementById('num-bots');
    
    // Generate initial bot selectors
    generateBotSelectors(parseInt(numBotsSelect.value));
    
    // Update bot selectors when number changes
    numBotsSelect.addEventListener('change', (e) => {
        generateBotSelectors(parseInt(e.target.value));
    });
    
    // Handle form submission
    document.getElementById('practice-setup-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const errorDiv = document.getElementById('error-message');
        const submitBtn = e.target.querySelector('button[type="submit"]');
        
        // Disable button and show loading
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating game...';
        errorDiv.style.display = 'none';
        
        try {
            const formData = new FormData(e.target);
            const numBots = parseInt(formData.get('num_bots'));
            
            // Build bot configurations
            const bots = [];
            for (let i = 1; i <= numBots; i++) {
                bots.push({
                    difficulty: formData.get(`bot_${i}_difficulty`) || 'intermediate'
                });
            }
            
            // Create practice room
            const response = await fetch('/api/lobby/rooms/create/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                },
                body: JSON.stringify({
                    mode: 'practice',
                    target_score: parseInt(formData.get('target_score')),
                    max_players: numBots + 1,
                    bots: bots
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
            // Practice game created - redirect to game
            if (data.game_id) {
                window.location.href = `/game/${data.game_id}/`;
            } else {
                // Fallback for room-based response
                window.location.href = `/game/${data.room_id || data.id}/`;
            }
        } else {
                // Show error
                errorDiv.textContent = data.error || 'Failed to create game. Please try again.';
                errorDiv.style.display = 'block';
                submitBtn.disabled = false;
                submitBtn.textContent = 'Start Practice Game';
            }
        } catch (error) {
            console.error('Practice setup error:', error);
            errorDiv.textContent = 'An error occurred. Please try again.';
            errorDiv.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.textContent = 'Start Practice Game';
        }
    });
});