"""
Utility functions for game functionality.
"""
import uuid
from typing import Dict, List, Optional, Any
from django.contrib.sessions.backends.db import SessionStore


def get_or_create_guest_identity(request):
    """
    Get or create a guest identity for unauthenticated users.
    Stores guest info in session.
    
    Returns:
        tuple: (is_guest: bool, user_or_none, guest_name: str)
    """
    if request.user.is_authenticated:
        return False, request.user, None
    
    # Check if guest already has session identity
    if 'guest_id' not in request.session:
        guest_id = uuid.uuid4().hex[:8]
        request.session['guest_id'] = guest_id
        request.session['guest_name'] = f"Guest_{guest_id}"
        request.session.save()
    
    guest_name = request.session.get('guest_name', 'Guest')
    
    return True, None, guest_name


def clear_guest_identity(request):
    """Clear guest identity from session."""
    if 'guest_id' in request.session:
        del request.session['guest_id']
    if 'guest_name' in request.session:
        del request.session['guest_name']
    request.session.save()


class IDMapper:
    """
    Maps between UUID strings (DB) and integer IDs (engine).
    This maintains a bidirectional mapping for the duration of a game.
    """
    
    def __init__(self, players: List[Any]):
        """
        Initialize mapper with list of player objects.
        
        Args:
            players: List of player objects with .id (UUID) attribute
                   These can be GamePlayer instances or any object with an id
        """
        self.uuid_to_int: Dict[str, int] = {}
        self.int_to_uuid: Dict[int, str] = {}
        
        for idx, player in enumerate(players):
            uuid_str = str(player.id)
            int_id = idx + 1  # 1-based indexing for engine
            self.uuid_to_int[uuid_str] = int_id
            self.int_to_uuid[int_id] = uuid_str
    
    def get_int(self, uuid_str: Optional[str]) -> Optional[int]:
        """Convert UUID string to integer ID."""
        if not uuid_str:
            return None
        return self.uuid_to_int.get(uuid_str)
    
    def get_int_required(self, uuid_str: str) -> int:
        """Convert UUID string to integer ID, raises KeyError if not found."""
        return self.uuid_to_int[uuid_str]
    
    def get_uuid(self, int_id: Optional[int]) -> Optional[str]:
        """Convert integer ID to UUID string."""
        if not int_id:
            return None
        return self.int_to_uuid.get(int_id)
    
    def get_uuid_required(self, int_id: int) -> str:
        """Convert integer ID to UUID string, raises KeyError if not found."""
        return self.int_to_uuid[int_id]
    
    def map_play_dict(self, play: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map player_id in a play dict from UUID (string) to int.
        
        Example:
            {'player_id': '123e4567-e89b-12d3-a456-426614174000', 'card': {...}}
            -> {'player_id': 1, 'card': {...}}
        """
        if 'player_id' in play and play['player_id']:
            play = play.copy()
            play['player_id'] = self.get_int_required(str(play['player_id']))
        return play
    
    def unmap_play_dict(self, play: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map player_id in a play dict from int to UUID (string).
        
        Example:
            {'player_id': 1, 'card': {...}}
            -> {'player_id': '123e4567-e89b-12d3-a456-426614174000', 'card': {...}}
        """
        if 'player_id' in play and play['player_id']:
            play = play.copy()
            play['player_id'] = self.get_uuid_required(int(play['player_id']))
        return play
    
    def map_player_list(self, player_ids: List[str]) -> List[int]:
        """Convert list of UUID strings to list of integer IDs."""
        return [self.get_int_required(pid) for pid in player_ids if pid]
    
    def unmap_player_list(self, int_ids: List[int]) -> List[str]:
        """Convert list of integer IDs to list of UUID strings."""
        return [self.get_uuid_required(iid) for iid in int_ids if iid]
    
    def map_hand_dict(self, hands: Dict[str, Any]) -> Dict[int, Any]:
        """
        Convert hands dict from UUID keys to integer keys.
        
        Args:
            hands: Dictionary with UUID string keys and hand values
        
        Returns:
            Dictionary with integer keys and same hand values
        """
        return {
            self.get_int_required(pid): hand_value
            for pid, hand_value in hands.items()
            if self.get_int(pid) is not None
        }
    
    def unmap_hand_dict(self, int_hands: Dict[int, Any]) -> Dict[str, Any]:
        """
        Convert hands dict from integer keys to UUID keys.
        
        Args:
            int_hands: Dictionary with integer keys and hand values
        
        Returns:
            Dictionary with UUID string keys and same hand values
        """
        return {
            self.get_uuid_required(pid): hand_value
            for pid, hand_value in int_hands.items()
            if self.get_uuid(pid) is not None
        }
    
    def create_mapping_metadata(self) -> Dict[str, str]:
        """
        Create a reverse mapping for debugging/logging purposes.
        Returns mapping from int ID to UUID string.
        """
        return {
            str(int_id): uuid_str
            for int_id, uuid_str in self.int_to_uuid.items()
        }