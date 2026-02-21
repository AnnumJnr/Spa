"""
Beginner bot - plays randomly from valid cards.
"""
import random
from typing import List
from apps.game.engine.card import Card
from apps.game.engine.state import GameState, SetState
from .base_bot import BaseBot


class BeginnerBot(BaseBot):
    """
    Beginner difficulty bot.
    
    Strategy:
    - Plays random valid cards
    - Never stacks
    - No strategic thinking
    """
    
    def choose_card(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> Card:
        """Choose a random valid card."""
        current_round = set_state.get_current_round()
        lead_suit = current_round.lead_suit if current_round else None
        
        valid_cards = self.get_valid_cards(hand, lead_suit)
        
        # Pick random card
        return random.choice(valid_cards)
    
    def should_stack(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> bool:
        """Beginner never stacks."""
        return False
    
    def choose_stack_cards(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> List[Card]:
        """Should never be called for beginner."""
        return []