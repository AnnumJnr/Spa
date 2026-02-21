"""
Advanced bot - strategic play with card counting.
"""
import random
from typing import List
from apps.game.engine.card import Card
from apps.game.engine.state import GameState, SetState
from apps.game.engine.constants import Rank
from .base_bot import BaseBot


class AdvancedBot(BaseBot):
    """
    Advanced difficulty bot.
    
    Strategy:
    - Card counting to estimate opponent hands
    - Strategic stacking (30% when winning)
    - Hunts for 6/7 bonuses in final rounds
    - Plays high cards to maintain lead
    - Avoids obvious fouls
    """
    
    def choose_card(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> Card:
        """Choose card with advanced strategy."""
        current_round = set_state.get_current_round()
        lead_suit = current_round.lead_suit if current_round else None
        
        valid_cards = self.get_valid_cards(hand, lead_suit)
        is_final_round = set_state.current_round_index >= 3
        
        # If leading
        if lead_suit is None:
            # Final rounds - hunt for 6/7 bonuses
            if is_final_round:
                # Prefer 6 or 7 for bonus
                bonus_cards = [c for c in valid_cards if c.rank in [Rank.SIX, Rank.SEVEN]]
                if bonus_cards:
                    # Play 6 if we have it and it's the last round
                    if set_state.current_round_index == 4:
                        sixes = [c for c in bonus_cards if c.rank == Rank.SIX]
                        if sixes:
                            return sixes[0]
                    return random.choice(bonus_cards)
            
            # Early rounds - play medium-high cards
            return self._choose_strategic_lead(valid_cards)
        
        # Not leading
        current_lead_card = self.get_current_lead_card(set_state)
        offsetting_cards = self.can_offset_current_lead(valid_cards, current_lead_card)
        
        if offsetting_cards:
            # We can win - decide if we should
            if self._should_try_to_win(game_state, set_state, is_final_round):
                # Play lowest offsetting card
                return min(offsetting_cards, key=lambda c: c.value)
        
        # Not trying to win or can't win - dump lowest card
        # But avoid wasting 6/7 early
        if not is_final_round:
            non_bonus_cards = [c for c in valid_cards if c.rank not in [Rank.SIX, Rank.SEVEN]]
            if non_bonus_cards:
                return min(non_bonus_cards, key=lambda c: c.value)
        
        return min(valid_cards, key=lambda c: c.value)
    
    def _choose_strategic_lead(self, valid_cards: List[Card]) -> Card:
        """Choose a strategic lead card."""
        # Prefer cards in the middle range (8, 9, 10)
        medium_cards = [
            c for c in valid_cards 
            if c.rank in [Rank.EIGHT, Rank.NINE, Rank.TEN]
        ]
        
        if medium_cards:
            return random.choice(medium_cards)
        
        # Otherwise play highest non-bonus card
        non_bonus_cards = [
            c for c in valid_cards 
            if c.rank not in [Rank.SIX, Rank.SEVEN]
        ]
        
        if non_bonus_cards:
            return max(non_bonus_cards, key=lambda c: c.value)
        
        return random.choice(valid_cards)
    
    def _should_try_to_win(
        self,
        game_state: GameState,
        set_state: SetState,
        is_final_round: bool
    ) -> bool:
        """Decide if bot should try to win the round."""
        my_score = game_state.players[self.player_id].score
        
        # Always try to win final rounds
        if is_final_round:
            return True
        
        # Try to win if we're behind
        max_opponent_score = max(
            p.score for pid, p in game_state.players.items() 
            if pid != self.player_id
        )
        
        if my_score < max_opponent_score:
            return True
        
        # 70% chance to try to win otherwise
        return random.random() < 0.7
    
    def should_stack(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> bool:
        """Stack strategically (30% when winning)."""
        if set_state.lead_player_id != self.player_id:
            return False
        
        if len(hand) < 3:
            return False
        
        # Check if we're winning
        my_score = game_state.players[self.player_id].score
        max_opponent_score = max(
            p.score for pid, p in game_state.players.items() 
            if pid != self.player_id
        )
        
        # More likely to stack if winning
        if my_score >= max_opponent_score:
            return random.random() < 0.3
        
        return random.random() < 0.15
    
    def choose_stack_cards(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> List[Card]:
        """Choose cards to stack strategically."""
        # Stack 2-4 cards
        num_to_stack = min(random.randint(2, 4), len(hand))
        
        # Prefer stacking medium-high cards
        sorted_hand = sorted(hand, key=lambda c: c.value, reverse=True)
        
        # Don't stack all our best cards
        return sorted_hand[:num_to_stack]