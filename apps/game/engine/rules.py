"""
Game rules engine: foul detection and offset logic.
Now includes stack foul detection.
"""
from typing import List, Dict, Tuple, Optional
from .card import Card
from .state import GameState, SetState, RoundState
from .constants import Scoring
from .stack import StackManager


class FoulResult:
    """Result of a foul check."""
    
    def __init__(
        self,
        fouling_players: List[int],
        reason: str = "",
        set_ended: bool = False
    ):
        self.fouling_players = fouling_players
        self.reason = reason
        self.set_ended = set_ended
    
    def has_fouls(self) -> bool:
        return len(self.fouling_players) > 0
    
    def to_dict(self) -> Dict:
        return {
            "fouling_players": self.fouling_players,
            "reason": self.reason,
            "set_ended": self.set_ended
        }


class OffsetResult:
    """Result of an offset check."""
    
    def __init__(
        self,
        offset_occurred: bool,
        new_lead_player_id: Optional[int] = None,
        offsetting_card: Optional[Card] = None
    ):
        self.offset_occurred = offset_occurred
        self.new_lead_player_id = new_lead_player_id
        self.offsetting_card = offsetting_card
    
    def to_dict(self) -> Dict:
        return {
            "offset_occurred": self.offset_occurred,
            "new_lead_player_id": self.new_lead_player_id,
            "offsetting_card": self.offsetting_card.to_dict() if self.offsetting_card else None
        }


class RuleEngine:
    """Implements Spa game rules for fouls and offsets."""
    
    @staticmethod
    def check_fouls(
        set_state: SetState,
        round_state: RoundState
    ) -> FoulResult:
        """
        Check for fouls after all players have played in a round.
        Now includes stack fouls.
        
        A foul occurs when:
        - Player plays wrong suit
        - While still having the lead suit in hand
        - Stack foul: auto-played card from interrupted stack violates suit-following
        """
        fouling_players = []
        lead_suit = round_state.lead_suit
        foul_reason = ""
        
        if lead_suit is None:
            return FoulResult(fouling_players)
        
        # Check each play for normal suit fouls
        for play in round_state.plays:
            player_id = play.player_id
            card = play.card
            
            # Skip the lead player's first card (sets the suit)
            if player_id == round_state.lead_player_id and len(round_state.plays) == 1:
                continue
            
            # Check if player played wrong suit
            if card.suit != lead_suit:
                # Check if player still had the lead suit
                hand = set_state.hands.get(player_id)
                if hand and hand.has_suit(lead_suit):
                    fouling_players.append(player_id)
                    foul_reason = "played_wrong_suit"
                    print(f"  ⚠️ FOUL: Player {player_id} played {card.suit} but must follow {lead_suit}")
        
        # Check for stack fouls (if there's an active/interrupted stack)
        if set_state.stack_state and set_state.stack_state.interrupted:
            stacker_id = set_state.stack_state.owner_player_id
            
            # Find if the stacker played this round (auto-play)
            stacker_play = None
            for play in round_state.plays:
                if play.player_id == stacker_id:
                    stacker_play = play
                    break
            
            if stacker_play:
                # This is an auto-played card - check for stack foul
                if StackManager.check_stack_foul(
                    set_state, 
                    round_state, 
                    stacker_id, 
                    stacker_play.card
                ):
                    fouling_players.append(stacker_id)
                    foul_reason = "stack_foul"
                    print(f"  ⚠️ STACK FOUL: Player {stacker_id} from interrupted stack")
        
        return FoulResult(
            fouling_players=fouling_players,
            reason=foul_reason if fouling_players else "",
            set_ended=len(fouling_players) > 0
        )
    
    @staticmethod
    def check_stack_foul(
        set_state: SetState,
        round_state: RoundState,
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
            print(f"    Stack foul: Player {stacker_id} committed {committed_card} but has {lead_suit} cards")
            return True
        
        return False
    
    @staticmethod
    def check_offset(
        current_lead_player_id: int,
        current_lead_card: Optional[Card],
        player_id: int,
        played_card: Card
    ) -> OffsetResult:
        """
        Check if a played card offsets the current lead.
        
        Offset occurs when:
        - Same suit as current lead
        - Higher value than current lead
        """
        if current_lead_card is None:
            # First card played becomes the lead
            return OffsetResult(
                offset_occurred=True,
                new_lead_player_id=player_id,
                offsetting_card=played_card
            )
        
        # Check if same suit and higher value
        if (played_card.suit == current_lead_card.suit and 
            played_card.value > current_lead_card.value):
            return OffsetResult(
                offset_occurred=True,
                new_lead_player_id=player_id,
                offsetting_card=played_card
            )
        
        # No offset
        return OffsetResult(offset_occurred=False)
    
    @staticmethod
    def apply_foul_penalties(
        game_state: GameState,
        set_state: SetState,
        fouling_players: List[int]
    ) -> Dict[int, int]:
        """
        Apply foul penalties and update game state.
        
        Returns:
            Dictionary of player_id -> score_change
        """
        score_changes = {}
        num_players = len(game_state.turn_order)
        
        if num_players == 2:
            # 2-player game rules
            if len(fouling_players) == 1:
                fouling_player = fouling_players[0]
                
                # Fouling player: -3
                game_state.players[fouling_player].score += Scoring.FOUL_PENALTY
                score_changes[fouling_player] = Scoring.FOUL_PENALTY
                
                # Other player: +1
                other_player = [p for p in game_state.turn_order if p != fouling_player][0]
                game_state.players[other_player].score += Scoring.NON_FOULING_BONUS_2P
                score_changes[other_player] = Scoring.NON_FOULING_BONUS_2P
                
                # Set ends immediately
                set_state.status = "ended"
                print(f"  Set ended due to foul by {fouling_player}")
        
        else:
            # 3-4 player game rules
            for player_id in fouling_players:
                # All fouling players: -3 each
                game_state.players[player_id].score += Scoring.FOUL_PENALTY
                score_changes[player_id] = Scoring.FOUL_PENALTY
                
                # Remove from active players
                if player_id in set_state.active_players:
                    set_state.active_players.remove(player_id)
                    print(f"  Player {player_id} removed from active players (fouled out)")
            
            # If only one player remains, they win the set
            if len(set_state.active_players) == 1:
                set_state.status = "ended"
                print(f"  Set ended - only one player remains active")
        
        return score_changes