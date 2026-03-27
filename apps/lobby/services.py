"""
Lobby and matchmaking services.
"""
from typing import Optional, TYPE_CHECKING
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import GameRoom, RoomPlayer, MatchmakingQueue
from apps.game.services import GameService
from apps.bots.models import BotProfile

if TYPE_CHECKING:
    from apps.accounts.models import User
else:
    User = get_user_model()


class RoomService:

    @staticmethod
    @transaction.atomic
    def create_room(
        mode: str,
        target_score: int = 12,
        max_players: int = 4,
        host_user=None,
        host_guest_name: str = None,
    ) -> tuple:
        """
        Create a private room. Returns (room, room_player).
        Either host_user (authenticated) or host_guest_name (guest) must be provided.
        """
        room = GameRoom.objects.create(
            host=host_user,  # null for guests
            mode=mode,
            target_score=target_score,
            max_players=max_players,
            status=GameRoom.STATUS_WAITING,
        )

        room_player = RoomPlayer.objects.create(
            room=room,
            user=host_user,
            guest_name=host_guest_name if not host_user else None,
            is_host=True,
            status=RoomPlayer.STATUS_ACTIVE,
            is_ready=True,
        )

        return room, room_player

    @staticmethod
    @transaction.atomic
    def join_room(
        room: GameRoom,
        user=None,
        guest_name: str = None,
    ) -> RoomPlayer:
        """
        Add a human player to a room.
        Either user (authenticated) or guest_name must be provided.
        """
        if room.is_full:
            raise ValueError("Room is full")

        if room.status != GameRoom.STATUS_WAITING:
            raise ValueError("Room is not accepting players")

        # Uniqueness checks
        if user:
            if RoomPlayer.objects.filter(
                room=room, user=user, status=RoomPlayer.STATUS_ACTIVE
            ).exists():
                raise ValueError("You are already in this room")
        else:
            if not guest_name or not guest_name.strip():
                raise ValueError("Guest name is required")
            guest_name = guest_name.strip()
            if RoomPlayer.objects.filter(
                room=room,
                guest_name__iexact=guest_name,
                status=RoomPlayer.STATUS_ACTIVE,
            ).exists():
                raise ValueError("That name is already taken in this room")

        room_player = RoomPlayer.objects.create(
            room=room,
            user=user,
            guest_name=guest_name if not user else None,
            is_host=False,
            status=RoomPlayer.STATUS_ACTIVE,
            is_ready=False,
        )

        return room_player

    @staticmethod
    @transaction.atomic
    def add_bot_to_room(room: GameRoom, difficulty: str = 'intermediate') -> RoomPlayer:
        if room.is_full:
            raise ValueError("Room is full")

        room_player = RoomPlayer.objects.create(
            room=room,
            user=None,
            is_bot=True,
            bot_difficulty=difficulty,
            status=RoomPlayer.STATUS_ACTIVE,
            is_ready=True,
        )
        return room_player

    @staticmethod
    @transaction.atomic
    def remove_bot_from_room(room: GameRoom) -> bool:
        """Remove the most recently added bot from the room."""
        bot = room.room_players.filter(
            is_bot=True, status=RoomPlayer.STATUS_ACTIVE
        ).order_by('-joined_at').first()
        if bot:
            bot.delete()
            return True
        return False

    @staticmethod
    @transaction.atomic
    def start_game(room: GameRoom) -> GameRoom:
        if not room.can_start:
            raise ValueError("Need at least 2 players to start")

        if room.status not in (GameRoom.STATUS_WAITING, GameRoom.STATUS_STARTING):
            raise ValueError("Room already started")

        active_players = room.room_players.filter(status=RoomPlayer.STATUS_ACTIVE)

        players = []
        for rp in active_players:
            players.append({
                'user': rp.user,
                'is_bot': rp.is_bot,
                'bot_difficulty': rp.bot_difficulty,
                'is_guest': rp.is_guest,
                'guest_name': rp.guest_name,
            })

        is_practice = room.mode == GameRoom.MODE_PRACTICE
        game = GameService.create_game(
            players=players,
            target_score=room.target_score,
            is_practice=is_practice,
        )
        GameService.start_game(game)

        room.game = game
        room.status = GameRoom.STATUS_IN_PROGRESS
        room.started_at = timezone.now()
        room.save()

        return room

    @staticmethod
    @transaction.atomic
    def leave_room(room_player: RoomPlayer) -> None:
        room_player.status = RoomPlayer.STATUS_LEFT
        room_player.left_at = timezone.now()
        room_player.save()

        room = room_player.room

        # If nobody active remains, close the room
        if not room.room_players.filter(status=RoomPlayer.STATUS_ACTIVE, is_bot=False).exists():
            room.status = GameRoom.STATUS_FINISHED
            room.finished_at = timezone.now()
            room.save()

    @staticmethod
    @transaction.atomic
    def finish_room(room: GameRoom) -> None:
        """Mark room as finished after the game ends."""
        room.status = GameRoom.STATUS_FINISHED
        room.finished_at = timezone.now()
        room.save()


class MatchmakingService:

    @staticmethod
    @transaction.atomic
    def enter_queue(user, mode: str = 'quick_match', target_score: int = 12):
        existing = MatchmakingQueue.objects.filter(user=user, is_matched=False).first()
        if existing:
            return existing

        entry = MatchmakingQueue.objects.create(
            user=user, mode=mode, target_score=target_score, is_matched=False
        )
        MatchmakingService.process_queue(mode, target_score)
        return entry

    @staticmethod
    @transaction.atomic
    def process_queue(mode: str, target_score: int):
        entries = MatchmakingQueue.objects.filter(
            mode=mode, target_score=target_score, is_matched=False
        ).order_by('joined_queue_at')

        if mode == 'quick_match' and entries.count() >= 2:
            matched = list(entries[:2])
            room, _ = RoomService.create_room(
                mode=GameRoom.MODE_QUICK_MATCH,
                target_score=target_score,
                max_players=2,
                host_user=matched[0].user,
            )
            RoomService.join_room(room, user=matched[1].user)
            for entry in matched:
                entry.is_matched = True
                entry.matched_room = room
                entry.matched_at = timezone.now()
                entry.save()
            return room

        elif mode == 'multiplayer' and entries.count() >= 2:
            matched = list(entries[:4])
            room, _ = RoomService.create_room(
                mode=GameRoom.MODE_MULTIPLAYER,
                target_score=target_score,
                max_players=4,
                host_user=matched[0].user,
            )
            for entry in matched[1:]:
                RoomService.join_room(room, user=entry.user)
            for entry in matched:
                entry.is_matched = True
                entry.matched_room = room
                entry.matched_at = timezone.now()
                entry.save()
            room.start_countdown()
            return room

        return None

    @staticmethod
    @transaction.atomic
    def leave_queue(user) -> None:
        MatchmakingQueue.objects.filter(user=user, is_matched=False).delete()