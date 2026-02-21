"""
Expert bot - advanced tactics and probability calculations.
"""
import random
from typing import List, Dict
from apps.game.engine.card import Card
from apps.game.engine.state import GameState, SetState
from apps.game.engine.constants import Rank
from .base_bot import BaseBot


class ExpertBot(BaseBot):
    """
    Expert difficulty bot.
    
    Strategy:
    - Advanced card counting and probability
    - Foul baiting (tries to make opponents foul)
    - Optimal stack timing (50% when leading)
    - Steal bonus hunting (7 offsetting 6)
    - Calculated risk-taking
    - Traps opponents with suit switches
    """
    
    def choose_card(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> Card:
        """Choose card with expert strategy."""
        current_round = set_state.get_current_round()
        lead_suit = current_round.lead_suit if current_round else None
        
        valid_cards = self.get_valid_cards(hand, lead_suit)
        is_final_round = set_state.current_round_index >= 3
        
        # If leading
        if lead_suit is None:
            return self._choose_expert_lead(
                game_state, set_state, valid_cards, is_final_round
            )
        
        # Not leading
        return self._choose_expert_response(
            game_state, set_state, valid_cards, is_final_round
        )
    
    def _choose_expert_lead(
        self,
        game_state: GameState,
        set_state: SetState,
        valid_cards: List[Card],
        is_final_round: bool
    ) -> Card:
        """Choose optimal lead card."""
        # Final round - hunt for bonuses
        if set_state.current_round_index == 4:
            # Play 6 if we have it (for +3 or better)
            sixes = [c for c in valid_cards if c.rank == Rank.SIX]
            if sixes:
                return sixes[0]
            
            # Play 7 (for +2 or steal bonus)
            sevens = [c for c in valid_cards if c.rank == Rank.SEVEN]
            if sevens:
                return sevens[0]
        
        # Round 3 - set up for bonus combos
        if set_state.current_round_index == 3:
            # If we have 6 or 7, save them for next round
            bonus_cards = [c for c in valid_cards if c.rank in [Rank.SIX, Rank.SEVEN]]
            non_bonus = [c for c in valid_cards if c not in bonus_cards]
            
            if non_bonus and bonus_cards:
                # Play high non-bonus to maintain lead
                return max(non_bonus, key=lambda c: c.value)
        
        # Try to bait fouls - lead with suit opponents might not have
        likely_exhausted_suit = self._find_likely_exhausted_suit()
        if likely_exhausted_suit:
            suit_cards = [c for c in valid_cards if c.suit == likely_exhausted_suit]
            if suit_cards:
                # Play lowest of that suit to bait foul
                return min(suit_cards, key=lambda c: c.value)
        
        # Play strong lead card
        return max(valid_cards, key=lambda c: c.value)
    
    def _choose_expert_response(
        self,
        game_state: GameState,
        set_state: SetState,
        valid_cards: List[Card],
        is_final_round: bool
    ) -> Card:
        """Choose optimal response card."""
        current_lead_card = self.get_current_lead_card(set_state)
        offsetting_cards = self.can_offset_current_lead(valid_cards, current_lead_card)
        
        # Check for steal bonus opportunity (7 offsetting 6 in final round)
        if (set_state.current_round_index == 4 and 
            current_lead_card and 
            current_lead_card.rank == Rank.SIX):
            sevens = [c for c in offsetting_cards if c.rank == Rank.SEVEN]
            if sevens:
                # Steal bonus! (+3 for 6, +1 steal = +4)
                return sevens[0]
        
        # Final rounds - be aggressive
        if is_final_round and offsetting_cards:
            # Calculate if winning is worth it
            if self._is_worth_winning(game_state, set_state):
                # Play lowest offsetting card
                return min(offsetting_cards, key=lambda c: c.value)
        
        # Non-final rounds
        if offsetting_cards:
            # Win if we're behind or it's strategic
            my_score = game_state.players[self.player_id].score
            lead_player_id = set_state.lead_player_id
            lead_score = game_state.players[lead_player_id].score
            
            if my_score < lead_score or random.random() < 0.8:
                return min(offsetting_cards, key=lambda c: c.value)
        
        # Can't or won't win - dump lowest card
        # But preserve 6/7 if possible
        if not is_final_round:
            non_bonus = [c for c in valid_cards if c.rank not in [Rank.SIX, Rank.SEVEN]]
            if non_bonus:
                return min(non_bonus, key=lambda c: c.value)
        
        return min(valid_cards, key=lambda c: c.value)
    
    def _find_likely_exhausted_suit(self) -> str:
        """Find suit that opponents likely don't have."""
        from apps.game.engine.constants import Suit
        
        # Check which suits we've seen the most of
        if not self.suit_counts:
            return None
        
        # Sort by how many we've seen
        sorted_suits = sorted(
            self.suit_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # If we've seen 6+ of a suit, opponents might be out
        if sorted_suits and sorted_suits[0][1] >= 6:
            return sorted_suits[0][0]
        
        return None
    
    def _is_worth_winning(
        self,
        game_state: GameState,
        set_state: SetState
    ) -> bool:
        """Calculate if winning this round is strategically valuable."""
        # Always win final round
        if set_state.current_round_index == 4:
            return True
        
        my_score = game_state.players[self.player_id].score
        
        # Calculate score differential
        other_scores = [
            p.score for pid, p in game_state.players.items() 
            if pid != self.player_id
        ]
        
        max_other = max(other_scores) if other_scores else 0
        
        # Win if behind
        if my_score < max_other:
            return True
        
        # Win if significantly ahead (to end set quickly)
        if my_score > max_other + 3:
            return True
        
        # 85% chance otherwise
        return random.random() < 0.85
    
    def should_stack(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> bool:
        """Stack strategically when leading (50% chance)."""
        if set_state.lead_player_id != self.player_id:
            return False
        
        if len(hand) < 3:
            return False
        
        # Don't stack in final 2 rounds (too risky)
        if set_state.current_round_index >= 3:
            return False
        
        # Check if we're winning
        my_score = game_state.players[self.player_id].score
        max_opponent_score = max(
            p.score for pid, p in game_state.players.items() 
            if pid != self.player_id
        )
        
        # Stack more often when winning
        if my_score >= max_opponent_score:
            return random.random() < 0.5
        
        return random.random() < 0.25
    
    def choose_stack_cards(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> List[Card]:
        """Choose optimal cards to stack."""
        # Stack 3-4 cards
        num_to_stack = min(random.randint(3, 4), len(hand))
        
        # Strategy: Stack high cards but keep one escape card
        sorted_hand = sorted(hand, key=lambda c: c.value, reverse=True)
        
        # Don't stack all Kings (keep one as safety)
        kings = [c for c in sorted_hand if c.rank == Rank.KING]
        if kings:
            # Keep one King, stack the rest
            stack_candidates = [c for c in sorted_hand if c != kings[0]]
            return stack_candidates[:num_to_stack]
        
        # Stack high-value cards
        return sorted_hand[:num_to_stack]