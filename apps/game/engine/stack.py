"""
Stacking mechanics implementation for Spa game.
Handles stack initiation, interruption, auto-play, and foul checking.
"""
from typing import List, Optional
from .card import Card
from .state import SetState, StackState
from .constants import StackConfig
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .state import RoundState

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
            cards: Cards to stack (in order of play) - NOTE: These are NOT removed from hand yet!
        
        Returns:
            Created StackState
        """
        print(f"\n=== STACK MANAGER: INITIATE STACK ===")
        print(f"Player {player_id} stacking {len(cards)} cards")
        
        # Create stack state
        stack_state = StackState(
            owner_player_id=player_id,
            stacked_cards=cards.copy(),
            start_round_index=set_state.current_round_index + 1,  # Starts next round
            interrupted=False,
            interruption_round=None
        )
        
        # CRITICAL FIX: Do NOT remove cards from hand here!
        # They will be removed when actually played in future rounds
        # The validator will check if the player still has them
        
        hand = set_state.hands.get(player_id)
        if hand:
            print(f"  Player hand has {len(hand.cards)} cards")
            print(f"  Stacked cards will be played in rounds {stack_state.start_round_index} onwards")
            # Verify player actually has these cards
            for card in cards:
                if not hand.has_card(card):
                    print(f"  WARNING: Player doesn't have {card} in hand!")
        
        # Mark player as having used stack
        set_state.stack_used_by.append(player_id)
        print(f"  Player {player_id} marked as used stack this set")
        
        # Set stack in set state
        set_state.stack_state = stack_state
        print(f"  Stack initiated: {len(cards)} cards starting round {stack_state.start_round_index}")
        print("=== END STACK MANAGER ===\n")
        
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
            print("  No active stack to interrupt")
            return
        
        # Only interrupt if interrupter is different from stack owner
        if interrupting_player_id == stack_state.owner_player_id:
            print(f"  Interrupter is stack owner - no interruption")
            return
        
        if stack_state.interrupted:
            print(f"  Stack already interrupted")
            return
        
        stack_state.interrupted = True
        stack_state.interruption_round = round_index
        print(f"  Stack interrupted by player {interrupting_player_id} at round {round_index}")
        print(f"  Remaining stacked cards: {len(stack_state.stacked_cards)} (become risky)")
    
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
        # Stack starts at start_round_index, so card 0 = start_round_index
        stack_card_index = round_index - stack_state.start_round_index
        
        if 0 <= stack_card_index < len(stack_state.stacked_cards):
            card = stack_state.stacked_cards[stack_card_index]
            print(f"  Found committed card for round {round_index}: {card}")
            return card
        
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
            print(f"  Auto-playing committed card for round {round_index}: {committed_card}")
            return committed_card
        
        # If stack was interrupted, still need to play committed cards
        # (They become risky commitments)
        if round_index >= stack_state.start_round_index:
            print(f"  Interrupted stack - auto-playing risky card for round {round_index}: {committed_card}")
            return committed_card
        
        return None
    
    @staticmethod
    def check_stack_foul(
        set_state: SetState,
        round_state: 'RoundState',  # Forward reference
        stacker_id: int,
        committed_card: Card
    ) -> bool:
        """
        Check if a stacker fouled due to interrupted stack.
        
        Stack foul occurs when ALL of these are true:
        1. Stack was interrupted
        2. A later round occurs with a committed card
        3. New lead calls a different suit
        4. Stacker still has the called suit in remaining hand
        
        Args:
            set_state: Current set state
            round_state: Current round state
            stacker_id: Player who stacked
            committed_card: Card being auto-played from stack
        
        Returns:
            True if stacker fouled
        """
        stack_state = set_state.stack_state
        if not stack_state or not stack_state.interrupted:
            return False
        
        lead_suit = round_state.lead_suit
        if lead_suit is None or committed_card.suit == lead_suit:
            return False
        
        # Check if stacker has the lead suit in their remaining hand
        hand = set_state.hands.get(stacker_id)
        if hand and hand.has_suit(lead_suit):
            print(f"  ⚠️ STACK FOUL: Player {stacker_id} committed {committed_card} but must follow {lead_suit}")
            return True
        
        return False
    
    @staticmethod
    def clear_stack(set_state: SetState) -> None:
        """Clear stack state (called at end of set)."""
        if set_state.stack_state:
            print(f"  Clearing stack for player {set_state.stack_state.owner_player_id}")
        set_state.stack_state = None
    
    @staticmethod
    def get_remaining_stacked_cards(
        set_state: SetState,
        player_id: int
    ) -> List[Card]:
        """
        Get all remaining stacked cards for a player.
        
        Args:
            set_state: Current set state
            player_id: Player to check
        
        Returns:
            List of remaining stacked cards
        """
        stack_state = set_state.stack_state
        if not stack_state or stack_state.owner_player_id != player_id:
            return []
        
        # Calculate which cards are still pending
        rounds_elapsed = set_state.current_round_index - stack_state.start_round_index
        if rounds_elapsed >= len(stack_state.stacked_cards):
            return []
        
        return stack_state.stacked_cards[rounds_elapsed:]