"""
WebSocket event builders and types.
"""
from typing import Dict, Any, Optional, List


class GameEvent:
    """Event type constants."""
    
    # Connection events
    PLAYER_CONNECTED = "player_connected"
    PLAYER_DISCONNECTED = "player_disconnected"
    
    # Game state events
    GAME_STARTED = "game_started"
    GAME_STATE = "game_state"
    GAME_ENDED = "game_ended"
    
    # Set events
    SET_STARTED = "set_started"
    SET_ENDED = "set_ended"
    
    # Round events
    ROUND_STARTED = "round_started"
    ROUND_ENDED = "round_ended"
    
    # Card play events
    CARD_PLAYED = "card_played"
    INVALID_PLAY = "invalid_play"
    YOUR_TURN = "your_turn"
    
    # Lead events
    LEAD_CHANGED = "lead_changed"
    
    # Stack events
    STACK_INITIATED = "stack_initiated"
    STACK_INTERRUPTED = "stack_interrupted"
    STACK_GAUGE_UPDATE = "stack_gauge_update"
    
    # Foul events
    FOUL_DETECTED = "foul_detected"
    
    # Score events
    SCORE_UPDATE = "score_update"
    
    # Error events
    ERROR = "error"


class EventBuilder:
    """Helper class to build standardized event payloads."""
    
    @staticmethod
    def build_event(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a standardized event payload.
        
        Args:
            event_type: Type of event
            data: Event data
        
        Returns:
            Event payload dictionary
        """
        return {
            "type": event_type,
            "data": data
        }
    
    @staticmethod
    def player_connected(player_id: str, display_name: str) -> Dict:
        """Player connected to game."""
        return EventBuilder.build_event(GameEvent.PLAYER_CONNECTED, {
            "player_id": player_id,  # Already string (UUID)
            "display_name": display_name
        })
    
    @staticmethod
    def player_disconnected(player_id: str) -> Dict:
        """Player disconnected from game."""
        return EventBuilder.build_event(GameEvent.PLAYER_DISCONNECTED, {
            "player_id": player_id  # Already string (UUID)
        })
    
    @staticmethod
    def game_started(game_state: Dict) -> Dict:
        """Game has started."""
        return EventBuilder.build_event(GameEvent.GAME_STARTED, {
            "game_state": game_state
        })
    
    @staticmethod
    def game_state(state: Dict) -> Dict:
        """Full game state update."""
        return EventBuilder.build_event(GameEvent.GAME_STATE, state)
    
    @staticmethod
    def game_ended(winner_id: str, final_scores: Dict[str, int]) -> Dict:
        """Game has ended."""
        return EventBuilder.build_event(GameEvent.GAME_ENDED, {
            "winner_id": winner_id,  # Already string (UUID)
            "final_scores": final_scores  # Already Dict[str, int]
        })
    
    @staticmethod
    def set_started(set_number: int, lead_player_id: str) -> Dict:
        """New set started."""
        return EventBuilder.build_event(GameEvent.SET_STARTED, {
            "set_number": set_number,
            "lead_player_id": lead_player_id  # Already string (UUID)
        })
    
    @staticmethod
    def set_ended(winner_id: str, score_awarded: int, new_scores: Dict[str, int]) -> Dict:
        """Set has ended."""
        return EventBuilder.build_event(GameEvent.SET_ENDED, {
            "winner_id": winner_id,  # Already string (UUID)
            "score_awarded": score_awarded,
            "new_scores": new_scores  # Already Dict[str, int]
        })
    
    @staticmethod
    def round_started(round_index: int, lead_player_id: str) -> Dict:
        """New round started."""
        return EventBuilder.build_event(GameEvent.ROUND_STARTED, {
            "round_index": round_index,
            "lead_player_id": lead_player_id  # Already string (UUID)
        })
    
    @staticmethod
    def card_played(
        player_id: str,
        card: Dict,
        round_complete: bool = False,
        next_player_id: Optional[str] = None
    ) -> Dict:
        """Card was played."""
        data = {
            "player_id": player_id,  # Already string (UUID)
            "card": card,
            "round_complete": round_complete
        }
        if next_player_id is not None:
            data["next_player_id"] = next_player_id  # Already string (UUID)
        return EventBuilder.build_event(GameEvent.CARD_PLAYED, data)
    
    @staticmethod
    def invalid_play(player_id: str, reason: str) -> Dict:
        """Invalid card play attempted."""
        return EventBuilder.build_event(GameEvent.INVALID_PLAY, {
            "player_id": player_id,  # Already string (UUID)
            "reason": reason
        })
    
    @staticmethod
    def your_turn(player_id: str) -> Dict:
        """It's a specific player's turn."""
        return EventBuilder.build_event(GameEvent.YOUR_TURN, {
            "player_id": player_id  # Already string (UUID)
        })
    
    @staticmethod
    def lead_changed(new_lead_player_id: str, offsetting_card: Optional[Dict] = None) -> Dict:
        """Lead player changed."""
        data = {
            "new_lead_player_id": new_lead_player_id  # Already string (UUID)
        }
        if offsetting_card is not None:
            data["offsetting_card"] = offsetting_card
        return EventBuilder.build_event(GameEvent.LEAD_CHANGED, data)
    
    @staticmethod
    def stack_initiated(player_id: str, num_cards: int) -> Dict:
        """Player initiated stacking."""
        return EventBuilder.build_event(GameEvent.STACK_INITIATED, {
            "player_id": player_id,  # Already string (UUID)
            "num_cards_stacked": num_cards
        })
    
    @staticmethod
    def stack_interrupted(interrupting_player_id: str, stack_owner_id: str) -> Dict:
        """Stack was interrupted."""
        return EventBuilder.build_event(GameEvent.STACK_INTERRUPTED, {
            "interrupting_player_id": interrupting_player_id,  # Already string (UUID)
            "stack_owner_id": stack_owner_id  # Already string (UUID)
        })
    
    @staticmethod
    def stack_gauge_update(player_id: str, gauge_percentage: int) -> Dict:
        """Stack gauge update."""
        return EventBuilder.build_event(GameEvent.STACK_GAUGE_UPDATE, {
            "player_id": player_id,  # Already string (UUID)
            "percentage": gauge_percentage
        })
    
    @staticmethod
    def foul_detected(fouling_players: List[str], reason: str, penalties: Dict[str, int]) -> Dict:
        """Foul was detected."""
        return EventBuilder.build_event(GameEvent.FOUL_DETECTED, {
            "fouling_players": fouling_players,  # Already List[str] (UUIDs)
            "reason": reason,
            "penalties": penalties  # Already Dict[str, int]
        })
    
    @staticmethod
    def score_update(scores: Dict[str, int]) -> Dict:
        """Score update."""
        return EventBuilder.build_event(GameEvent.SCORE_UPDATE, {
            "scores": scores  # Already Dict[str, int]
        })
    
    @staticmethod
    def error(message: str, code: Optional[str] = None) -> Dict:
        """Error occurred."""
        data = {"message": message}
        if code is not None:
            data["code"] = code
        return EventBuilder.build_event(GameEvent.ERROR, data)