"""State classes for game, set, and round."""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from .card import Card, Hand
from .constants import GameStatus, SetStatus


@dataclass
class Play:
    """A single card play in a round."""
    player_id: int
    card: Card
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "card": self.card.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Play':
        """Create a Play from a dictionary."""
        return cls(
            player_id=data["player_id"],
            card=Card.from_dict(data["card"])
        )


@dataclass
class PlayerState:
    """State for a single player in the game."""
    player_id: int
    score: int = 0
    is_active: bool = True  # False if fouled out
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "score": self.score,
            "is_active": self.is_active
        }


@dataclass
class StackState:
    """State for a player's stack commitment."""
    owner_player_id: int
    stacked_cards: List[Card] = field(default_factory=list)
    start_round_index: int = 0
    interrupted: bool = False
    interruption_round: Optional[int] = None
    
    def is_active(self) -> bool:
        """Check if stack is currently active."""
        return len(self.stacked_cards) > 0 and not self.interrupted
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "owner_player_id": self.owner_player_id,
            "stacked_cards": [card.to_dict() for card in self.stacked_cards],
            "start_round_index": self.start_round_index,
            "interrupted": self.interrupted,
            "interruption_round": self.interruption_round
        }


@dataclass
class RoundState:
    """State for a single internal round within a set."""
    round_index: int  # 0-4
    lead_player_id: int
    lead_suit: Optional[str] = None
    plays: List[Play] = field(default_factory=list)  # Now List[Play] instead of List[Dict]
    resolved: bool = False
    
    def add_play(self, player_id: int, card: Card) -> None:
        """Add a card play to this round."""
        self.plays.append(Play(player_id=player_id, card=card))
        
        # Set lead suit if this is the first play
        if self.lead_suit is None:
            self.lead_suit = card.suit
    
    def get_play_by_player(self, player_id: int) -> Optional[Play]:
        """Get the play made by a specific player."""
        for play in self.plays:
            if play.player_id == player_id:
                return play
        return None
    
    def has_played(self, player_id: int) -> bool:
        """Check if a player has played in this round."""
        return self.get_play_by_player(player_id) is not None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_index": self.round_index,
            "lead_player_id": self.lead_player_id,
            "lead_suit": self.lead_suit,
            "plays": [play.to_dict() for play in self.plays],
            "resolved": self.resolved
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoundState':
        """Create a RoundState from a dictionary."""
        round_state = cls(
            round_index=data["round_index"],
            lead_player_id=data["lead_player_id"],
            lead_suit=data.get("lead_suit"),
            resolved=data.get("resolved", False)
        )
        # Convert plays from dicts to Play objects
        for play_data in data.get("plays", []):
            round_state.plays.append(Play.from_dict(play_data))
        return round_state


@dataclass
class SetState:
    """State for a single set (5 rounds)."""
    set_id: str
    hands: Dict[int, Hand] = field(default_factory=dict)  # player_id -> Hand
    active_players: List[int] = field(default_factory=list)
    current_round_index: int = 0
    lead_player_id: int = 0
    rounds: List[RoundState] = field(default_factory=list)
    stack_state: Optional[StackState] = None
    stack_used_by: List[int] = field(default_factory=list)  # Players who used stack this set
    status: str = SetStatus.ACTIVE
    
    def get_current_round(self) -> Optional[RoundState]:
        """Get the current round state."""
        if 0 <= self.current_round_index < len(self.rounds):
            return self.rounds[self.current_round_index]
        return None
    
    def advance_round(self) -> None:
        """Move to the next round."""
        self.current_round_index += 1
    
    def is_complete(self) -> bool:
        """Check if all 5 rounds are complete."""
        return self.current_round_index >= 5
    
    def get_active_hand(self, player_id: int) -> Optional[Hand]:
        """Get a player's hand if they're active."""
        if player_id in self.active_players:
            return self.hands.get(player_id)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "set_id": self.set_id,
            "hands": {
                player_id: hand.to_dict()
                for player_id, hand in self.hands.items()
            },
            "active_players": self.active_players,
            "current_round_index": self.current_round_index,
            "lead_player_id": self.lead_player_id,
            "rounds": [round_state.to_dict() for round_state in self.rounds],
            "stack_state": self.stack_state.to_dict() if self.stack_state else None,
            "stack_used_by": self.stack_used_by,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], hands_data: Dict[int, List]) -> 'SetState':
        """Create a SetState from dictionary data."""
        set_state = cls(
            set_id=data["set_id"],
            active_players=data.get("active_players", []),
            current_round_index=data.get("current_round_index", 0),
            lead_player_id=data.get("lead_player_id", 0),
            stack_used_by=data.get("stack_used_by", []),
            status=data.get("status", SetStatus.ACTIVE)
        )
        
        # Load hands
        for player_id, hand_dict in hands_data.items():
            set_state.hands[player_id] = Hand.from_dict(hand_dict)
        
        # Load rounds
        for round_data in data.get("rounds", []):
            set_state.rounds.append(RoundState.from_dict(round_data))
        
        # Load stack state if present
        if data.get("stack_state"):
            stack_data = data["stack_state"]
            set_state.stack_state = StackState(
                owner_player_id=stack_data["owner_player_id"],
                stacked_cards=[Card.from_dict(c) for c in stack_data.get("stacked_cards", [])],
                start_round_index=stack_data.get("start_round_index", 0),
                interrupted=stack_data.get("interrupted", False),
                interruption_round=stack_data.get("interruption_round")
            )
        
        return set_state


@dataclass
class GameState:
    """Top-level game state."""
    game_id: str
    players: Dict[int, PlayerState] = field(default_factory=dict)  # player_id -> PlayerState
    target_score: int = 12
    current_set: Optional[SetState] = None
    lead_player_id: int = 0  # Current lead (persists across sets)
    status: str = GameStatus.WAITING
    turn_order: List[int] = field(default_factory=list)  # Clockwise player IDs
    
    def get_player(self, player_id: int) -> Optional[PlayerState]:
        """Get a player's state."""
        return self.players.get(player_id)
    
    def get_active_players(self) -> List[int]:
        """Get list of active player IDs."""
        return [
            player_id
            for player_id, player in self.players.items()
            if player.is_active
        ]
        
    def get_next_player(self, current_player_id: int) -> int:
        """
        Get the next player in clockwise order.
        Only returns active players.
        
        Args:
            current_player_id: Current player ID
        
        Returns:
            Next active player ID, or 0 if none found
        """
        try:
            if not self.turn_order:
                print("ERROR: No turn order in game_state")
                active_players = self.get_active_players()
                return active_players[0] if active_players else 0
            
            # Get list of active players
            active_players = self.get_active_players()
            if not active_players:
                print("ERROR: No active players found")
                return 0
            
            # Find current player in turn order
            try:
                current_index = self.turn_order.index(current_player_id)
            except ValueError:
                print(f"Current player {current_player_id} not in turn order")
                # Return first active player
                return active_players[0]
            
            # Look for next active player in clockwise order
            for i in range(1, len(self.turn_order) + 1):
                next_index = (current_index + i) % len(self.turn_order)
                next_player = self.turn_order[next_index]
                
                if next_player in active_players:
                    return next_player
            
            # No active players found after current
            print("WARNING: No active players found after current")
            return active_players[0] if active_players else 0
            
        except Exception as e:
            print(f"Error in get_next_player: {e}")
            active_players = self.get_active_players()
            return active_players[0] if active_players else 0
    
    def check_win_condition(self) -> Optional[int]:
        """Check if any player has won. Returns winner's player_id or None."""
        for player_id, player in self.players.items():
            if player.score >= self.target_score:
                return player_id
        return None
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Serialize game state to dictionary.
        
        Args:
            include_sensitive: If False, hides lead_player_id from output
        """
        data = {
            "game_id": self.game_id,
            "players": {
                player_id: player.to_dict()
                for player_id, player in self.players.items()
            },
            "target_score": self.target_score,
            "current_set": self.current_set.to_dict() if self.current_set else None,
            "status": self.status,
            "turn_order": self.turn_order
        }
        
        if include_sensitive:
            data["lead_player_id"] = self.lead_player_id
        
        return data