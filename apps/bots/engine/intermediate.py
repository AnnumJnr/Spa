"""
Intermediate bot - basic strategic play.
"""
import random
from typing import List
from apps.game.engine.card import Card
from apps.game.engine.state import GameState, SetState
from apps.game.engine.constants import Rank
from .base_bot import BaseBot


class IntermediateBot(BaseBot):
    """
    Intermediate difficulty bot.
    
    Strategy:
    - Plays high cards when winning
    - Saves low cards (6, 7) for potential bonuses
    - Occasionally stacks (10% chance)
    - Basic card counting
    """
    
    def choose_card(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> Card:
        """Choose card with basic strategy."""
        current_round = set_state.get_current_round()
        lead_suit = current_round.lead_suit if current_round else None
        
        valid_cards = self.get_valid_cards(hand, lead_suit)
        
        # If leading, prefer medium cards (save 6, 7 for later)
        if lead_suit is None:
            # Try to avoid playing 6 or 7 early in the set
            if set_state.current_round_index < 3:
                non_bonus_cards = [
                    c for c in valid_cards 
                    if c.rank not in [Rank.SIX, Rank.SEVEN]
                ]
                if non_bonus_cards:
                    return random.choice(non_bonus_cards)
            
            return random.choice(valid_cards)
        
        # Not leading - check if we can offset
        current_lead_card = self.get_current_lead_card(set_state)
        offsetting_cards = self.can_offset_current_lead(valid_cards, current_lead_card)
        
        if offsetting_cards:
            # We're winning - play lowest offsetting card
            return min(offsetting_cards, key=lambda c: c.value)
        else:
            # Can't win - play lowest card
            return min(valid_cards, key=lambda c: c.value)
    
    def should_stack(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> bool:
        """Stack 10% of the time when leading."""
        if set_state.lead_player_id != self.player_id:
            return False
        
        # Only stack if we have at least 3 cards
        if len(hand) < 3:
            return False
        
        # 10% chance to stack
        return random.random() < 0.1
    
    def choose_stack_cards(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> List[Card]:
        """Stack 2-3 random cards."""
        num_to_stack = min(random.randint(2, 3), len(hand))
        return random.sample(hand, num_to_stack)