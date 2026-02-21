"""
Stacking mechanics implementation.
"""
from typing import List, Optional
from .card import Card
from .state import SetState, StackState
from .constants import StackConfig


class StackManager:
    """Manages stacking mechanics."""
    
    @staticmethod
    def initiate_stack(
        set_state: SetState,
        player_id: int,
        cards: List[Card]
    ) -> StackState:
        """
        Initiate a stack for a player.
        
        Args:
            set_state: Current set state
            player_id: Player initiating stack
            cards: Cards to stack (in order of play)
        
        Returns:
            Created StackState
        """
        # Create stack state
        stack_state = StackState(
            owner_player_id=player_id,
            stacked_cards=cards.copy(),
            start_round_index=set_state.current_round_index + 1,  # Starts next round
            interrupted=False,
            interruption_round=None
        )
        
        # Remove stacked cards from player's hand
        hand = set_state.hands.get(player_id)
        if hand:
            for card in cards:
                if hand.has_card(card):
                    hand.remove_card(card)
        
        # Mark player as having used stack
        set_state.stack_used_by.append(player_id)
        
        # Set stack in set state
        set_state.stack_state = stack_state
        
        return stack_state
    
    @staticmethod
    def interrupt_stack(
        set_state: SetState,
        interrupting_player_id: int,
        round_index: int
    ) -> None:
        """
        Interrupt an active stack when another player offsets.
        
        Args:
            set_state: Current set state
            interrupting_player_id: Player who offset
            round_index: Round at which interrupt occurred
        """
        stack_state = set_state.stack_state
        if not stack_state:
            return
        
        # Only interrupt if interrupter is different from stack owner
        if interrupting_player_id == stack_state.owner_player_id:
            return
        
        stack_state.interrupted = True
        stack_state.interruption_round = round_index
    
    @staticmethod
    def get_committed_card(
        set_state: SetState,
        round_index: int
    ) -> Optional[Card]:
        """
        Get the committed card for a specific round if stack exists.
        
        Args:
            set_state: Current set state
            round_index: Round index to check
        
        Returns:
            Committed card or None
        """
        stack_state = set_state.stack_state
        if not stack_state or len(stack_state.stacked_cards) == 0:
            return None
        
        # Calculate which card in stack corresponds to this round
        stack_card_index = round_index - stack_state.start_round_index
        
        if 0 <= stack_card_index < len(stack_state.stacked_cards):
            return stack_state.stacked_cards[stack_card_index]
        
        return None
    
    @staticmethod
    def should_auto_play_from_stack(
        set_state: SetState,
        player_id: int,
        round_index: int
    ) -> Optional[Card]:
        """
        Check if a card should be auto-played from stack for this round.
        
        Args:
            set_state: Current set state
            player_id: Player to check
            round_index: Current round index
        
        Returns:
            Card to auto-play or None
        """
        stack_state = set_state.stack_state
        if not stack_state or stack_state.owner_player_id != player_id:
            return None
        
        # Get committed card for this round
        committed_card = StackManager.get_committed_card(set_state, round_index)
        if not committed_card:
            return None
        
        # If stack was not interrupted, auto-play
        if not stack_state.interrupted:
            return committed_card
        
        # If stack was interrupted, still need to play committed cards
        # (They become risky commitments)
        if round_index >= stack_state.start_round_index:
            return committed_card
        
        return None
    
    @staticmethod
    def clear_stack(set_state: SetState) -> None:
        """Clear stack state (called at end of set)."""
        set_state.stack_state = None