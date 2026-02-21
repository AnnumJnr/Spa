"""
Card play validation logic.
Validates whether a card play is legal given current game state.
"""
from typing import Optional, Tuple
from .card import Card, Hand
from .state import GameState, SetState, RoundState


class ValidationError(Exception):
    """Raised when a card play is invalid."""
    pass


class CardValidator:
    """Validates card plays against game rules."""
    
    @staticmethod
    def validate_card_play(
        game_state: GameState,
        set_state: SetState,
        player_id: int,
        card: Card
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a player can legally play a card.
        
        Returns:
            (is_valid, error_message)
        """
        # Check if game is active
        if game_state.status != "active":
            return False, "Game is not active"
        
        # Check if set is active
        if set_state.status != "active":
            return False, "Set is not active"
        
        # Check if player is active
        if player_id not in set_state.active_players:
            return False, "Player is not active in this set"
        
        # Check if player has the card
        hand = set_state.hands.get(player_id)
        if not hand or not hand.has_card(card):
            return False, "Player does not have this card"
        
        # Get current round
        current_round = set_state.get_current_round()
        if not current_round:
            return False, "No active round"
        
        # Check if player has already played this round
        if current_round.has_played(player_id):
            return False, "Player has already played this round"
        
        # Check suit-following rules (STRICT)
        lead_suit = current_round.lead_suit
        
        # If this is NOT the first play of the round (lead suit is set)
        if lead_suit is not None:
            # Player is NOT the lead, so must follow suit if possible
            if player_id != current_round.lead_player_id:
                if hand.has_suit(lead_suit) and card.suit != lead_suit:
                    return False, f"Must follow lead suit ({lead_suit})"
        
        # All validations passed
        return True, None
    
    @staticmethod
    def can_stack(
        game_state: GameState,
        set_state: SetState,
        player_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a player can initiate stacking.
        
        Returns:
            (can_stack, error_message)
        """
        # Player must be the lead OR have just offset
        if player_id != set_state.lead_player_id:
            return False, "Only the lead player can stack"
        
        # Player must not have used stack already this set
        if player_id in set_state.stack_used_by:
            return False, "Stack already used this set"
        
        # Must have cards remaining
        hand = set_state.hands.get(player_id)
        if not hand or len(hand) == 0:
            return False, "No cards to stack"
        
        # Must have remaining rounds
        remaining_rounds = 5 - set_state.current_round_index
        if remaining_rounds <= 0:
            return False, "No remaining rounds to stack"
        
        return True, None
    
    @staticmethod
    def validate_stack_cards(
        set_state: SetState,
        player_id: int,
        cards: list[Card]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate cards being stacked.
        
        Returns:
            (is_valid, error_message)
        """
        hand = set_state.hands.get(player_id)
        if not hand:
            return False, "Player has no hand"
        
        # Check if player has all the cards
        for card in cards:
            if not hand.has_card(card):
                return False, f"Player does not have card: {card}"
        
        # Check if number of cards exceeds remaining rounds
        remaining_rounds = 5 - set_state.current_round_index
        if len(cards) > remaining_rounds:
            return False, f"Cannot stack {len(cards)} cards with only {remaining_rounds} rounds remaining"
        
        # Check max stack size
        if len(cards) > 5:
            return False, "Cannot stack more than 5 cards"
        
        return True, None