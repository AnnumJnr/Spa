"""
Lobby and matchmaking services.
"""
from typing import List, Optional, TYPE_CHECKING
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import GameRoom, RoomPlayer, MatchmakingQueue
from apps.game.services import GameService
from apps.bots.models import BotProfile

# Type checking import - only used for type hints, not runtime
if TYPE_CHECKING:
    from apps.accounts.models import User
else:
    User = get_user_model()


class RoomService:
    """Service for room management."""
    
    @staticmethod
    @transaction.atomic
    def create_room(
        host: User,
        mode: str,
        target_score: int = 12,
        max_players: int = 4
    ) -> GameRoom:
        """
        Create a new game room.
        
        Args:
            host: User creating the room
            mode: Room mode (quick_match, multiplayer, private, practice)
            target_score: Target score for the game
            max_players: Maximum players allowed
        
        Returns:
            Created GameRoom instance
        """
        room = GameRoom.objects.create(
            host=host,
            mode=mode,
            target_score=target_score,
            max_players=max_players,
            status=GameRoom.STATUS_WAITING
        )
        
        # Add host as first player
        RoomPlayer.objects.create(
            room=room,
            user=host,
            status=RoomPlayer.STATUS_ACTIVE,
            is_ready=True if mode == GameRoom.MODE_PRIVATE else False
        )
        
        return room
    
    @staticmethod
    @transaction.atomic
    def join_room(room: GameRoom, user: User) -> RoomPlayer:
        """
        Add a player to a room.
        
        Args:
            room: Room to join
            user: User joining
        
        Returns:
            Created RoomPlayer instance
        """
        if room.is_full:
            raise ValueError("Room is full")
        
        if room.status != GameRoom.STATUS_WAITING:
            raise ValueError("Room is not accepting players")
        
        # Check if user already in room
        if RoomPlayer.objects.filter(room=room, user=user, status=RoomPlayer.STATUS_ACTIVE).exists():
            raise ValueError("User already in room")
        
        room_player = RoomPlayer.objects.create(
            room=room,
            user=user,
            status=RoomPlayer.STATUS_ACTIVE,
            is_ready=False
        )
        
        # Check if room should auto-start
        if room.mode == GameRoom.MODE_QUICK_MATCH and room.current_player_count == 2:
            RoomService.start_game(room)
        elif room.mode == GameRoom.MODE_MULTIPLAYER and not room.countdown_started_at:
            # Start countdown on first join
            room.start_countdown()
        elif room.mode == GameRoom.MODE_PRIVATE and room.is_full:
            # Auto-start if room reaches max capacity
            RoomService.start_game(room)
        
        return room_player
    
    @staticmethod
    @transaction.atomic
    def add_bot_to_room(
        room: GameRoom,
        difficulty: str = 'intermediate'
    ) -> RoomPlayer:
        """
        Add a bot player to a room.
        
        Args:
            room: Room to add bot to
            difficulty: Bot difficulty level
        
        Returns:
            Created RoomPlayer instance
        """
        if room.is_full:
            raise ValueError("Room is full")
        
        bot_profile = BotProfile.get_or_create_bot(difficulty)
        
        room_player = RoomPlayer.objects.create(
            room=room,
            user=None,
            is_bot=True,
            bot_difficulty=difficulty,
            status=RoomPlayer.STATUS_ACTIVE,
            is_ready=True
        )
        
        return room_player
    
    @staticmethod
    @transaction.atomic
    def start_game(room: GameRoom) -> GameRoom:
        """
        Start a game from a room.
        
        Args:
            room: Room to start game from
        
        Returns:
            Updated GameRoom instance
        """
        if not room.can_start:
            raise ValueError("Room cannot start yet")
        
        if room.status != GameRoom.STATUS_WAITING and room.status != GameRoom.STATUS_STARTING:
            raise ValueError("Room already started")
        
        # Get active players
        room_players = room.room_players.filter(status=RoomPlayer.STATUS_ACTIVE)
        
        # Build player list for game creation
        players = []
        for room_player in room_players:
            players.append({
                'user': room_player.user,
                'is_bot': room_player.is_bot,
                'bot_difficulty': room_player.bot_difficulty
            })
        
        # Create game
        is_practice = room.mode == GameRoom.MODE_PRACTICE
        game = GameService.create_game(
            players=players,
            target_score=room.target_score,
            is_practice=is_practice
        )
        
        # Start game
        GameService.start_game(game)
        
        # Link game to room
        room.game = game
        room.status = GameRoom.STATUS_IN_PROGRESS
        room.started_at = timezone.now()
        room.save()
        
        return room
    
    @staticmethod
    @transaction.atomic
    def leave_room(room_player: RoomPlayer) -> None:
        """
        Remove a player from a room.
        
        Args:
            room_player: RoomPlayer instance
        """
        room_player.status = RoomPlayer.STATUS_LEFT
        room_player.left_at = timezone.now()
        room_player.save()
        
        room = room_player.room
        
        # If host leaves and room hasn't started, cancel room
        if room_player.user == room.host and room.status == GameRoom.STATUS_WAITING:
            room.status = GameRoom.STATUS_FINISHED
            room.save()


class MatchmakingService:
    """Service for matchmaking."""
    
    @staticmethod
    @transaction.atomic
    def enter_queue(
        user: User,
        mode: str = 'quick_match',
        target_score: int = 12
    ) -> MatchmakingQueue:
        """
        Add a user to matchmaking queue.
        
        Args:
            user: User entering queue
            mode: Matchmaking mode
            target_score: Desired target score
        
        Returns:
            Created MatchmakingQueue entry
        """
        # Check if user already in queue
        existing = MatchmakingQueue.objects.filter(
            user=user,
            is_matched=False
        ).first()
        
        if existing:
            return existing
        
        entry = MatchmakingQueue.objects.create(
            user=user,
            mode=mode,
            target_score=target_score,
            is_matched=False
        )
        
        # Try to match immediately
        MatchmakingService.process_queue(mode, target_score)
        
        return entry
    
    @staticmethod
    @transaction.atomic
    def process_queue(mode: str, target_score: int) -> Optional[GameRoom]:
        """
        Process matchmaking queue and create games.
        
        Args:
            mode: Matchmaking mode
            target_score: Target score preference
        
        Returns:
            Created GameRoom if match found, else None
        """
        # Get unmatched entries for this mode/score
        entries = MatchmakingQueue.objects.filter(
            mode=mode,
            target_score=target_score,
            is_matched=False
        ).order_by('joined_queue_at')
        
        if mode == 'quick_match':
            # Need exactly 2 players
            if entries.count() >= 2:
                matched_entries = list(entries[:2])
                
                # Create room
                room = RoomService.create_room(
                    host=matched_entries[0].user,
                    mode=GameRoom.MODE_QUICK_MATCH,
                    target_score=target_score,
                    max_players=2
                )
                
                # Add second player
                RoomService.join_room(room, matched_entries[1].user)
                
                # Mark as matched
                for entry in matched_entries:
                    entry.is_matched = True
                    entry.matched_room = room
                    entry.matched_at = timezone.now()
                    entry.save()
                
                # Game auto-starts for quick match
                return room
        
        elif mode == 'multiplayer':
            # Need at least 2 players, up to 4
            if entries.count() >= 2:
                # Take up to 4 players
                matched_entries = list(entries[:4])
                
                # Create room
                room = RoomService.create_room(
                    host=matched_entries[0].user,
                    mode=GameRoom.MODE_MULTIPLAYER,
                    target_score=target_score,
                    max_players=4
                )
                
                # Add other players
                for entry in matched_entries[1:]:
                    RoomService.join_room(room, entry.user)
                
                # Mark as matched
                for entry in matched_entries:
                    entry.is_matched = True
                    entry.matched_room = room
                    entry.matched_at = timezone.now()
                    entry.save()
                
                # Start countdown (game starts after timer)
                room.start_countdown()
                
                return room
        
        return None
    
    @staticmethod
    @transaction.atomic
    def leave_queue(user: User) -> None:
        """
        Remove a user from matchmaking queue.
        
        Args:
            user: User leaving queue
        """
        MatchmakingQueue.objects.filter(
            user=user,
            is_matched=False
        ).delete()