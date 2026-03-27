"""
WebSocket consumer for private room lobby.
"""
import json
import asyncio
from typing import Optional
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .models import GameRoom, RoomPlayer
from .services import RoomService


class LobbyConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for private room lobby.
    URL: ws/lobby/room/<room_code>/
    Query param: ?guest_name=<name> for guests
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_code = None
        self.room_id = None
        self.room_group_name = None
        self.player_id = None
        self.display_name = None

    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs'].get('room_code')
        user = self.scope['user']

        # Parse guest_name from query string
        query_string = self.scope.get('query_string', b'').decode()
        params = {}
        if query_string:
            for part in query_string.split('&'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    params[k] = v
        guest_name = params.get('guest_name', '').strip()

        # Resolve identity
        try:
            result = await self.get_room_player(user, guest_name)
        except Exception as e:
            await self.close(code=4003)
            return

        if not result:
            await self.close(code=4003)
            return

        room, room_player = result
        self.room_id = str(room.id)
        self.room_group_name = f'room_{self.room_id}'
        self.player_id = str(room_player.id)
        self.display_name = room_player.display_name

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Send current room state to this player
        room_state = await self.build_room_state()
        await self.send(text_data=json.dumps({'type': 'room_state', 'data': room_state}))

        # Notify everyone else
        await self.channel_layer.group_send(
            self.room_group_name,
            {'type': 'player_joined_event', 'display_name': self.display_name,
             'room_state': room_state}
        )

    async def disconnect(self, close_code):
        if self.room_group_name:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if action == 'start_game':
                await self.handle_start_game()
            elif action == 'add_bot':
                await self.handle_add_bot(data)
            elif action == 'remove_bot':
                await self.handle_remove_bot()
            elif action == 'leave':
                await self.handle_leave()
            else:
                await self.send(text_data=json.dumps(
                    {'type': 'error', 'message': f'Unknown action: {action}'}
                ))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'Invalid JSON'}))
        except Exception as e:
            print(f"LobbyConsumer receive error: {e}")
            await self.send(text_data=json.dumps({'type': 'error', 'message': str(e)}))

    async def handle_start_game(self):
        result = await self.start_game_db()

        if not result['success']:
            await self.send(text_data=json.dumps(
                {'type': 'error', 'message': result['error']}
            ))
            return

        # Broadcast game starting to all in room
        await self.channel_layer.group_send(
            self.room_group_name,
            {'type': 'game_starting_event', 'game_id': result['game_id']}
        )

    async def handle_add_bot(self, data):
        difficulty = data.get('difficulty', 'intermediate')
        result = await self.add_bot_db(difficulty)

        if not result['success']:
            await self.send(text_data=json.dumps(
                {'type': 'error', 'message': result['error']}
            ))
            return

        room_state = await self.build_room_state()
        await self.channel_layer.group_send(
            self.room_group_name,
            {'type': 'room_updated_event', 'room_state': room_state}
        )

    async def handle_remove_bot(self):
        result = await self.remove_bot_db()
        room_state = await self.build_room_state()
        await self.channel_layer.group_send(
            self.room_group_name,
            {'type': 'room_updated_event', 'room_state': room_state}
        )

    async def handle_leave(self):
        await self.leave_room_db()
        room_state = await self.build_room_state()
        await self.channel_layer.group_send(
            self.room_group_name,
            {'type': 'player_left_event', 'display_name': self.display_name,
             'room_state': room_state}
        )
        await self.close()

    # ── Channel layer event handlers ──

    async def player_joined_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'player_joined',
            'display_name': event['display_name'],
            'room_state': event['room_state'],
        }))

    async def player_left_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'player_left',
            'display_name': event['display_name'],
            'room_state': event['room_state'],
        }))

    async def room_updated_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'room_updated',
            'room_state': event['room_state'],
        }))

    async def game_starting_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'game_starting',
            'game_id': event['game_id'],
        }))

    # ── DB helpers ──

    @database_sync_to_async
    def get_room_player(self, user, guest_name):
        """
        Resolve the RoomPlayer for this connection.
        For authenticated users: find by user.
        For guests: find by guest_name.
        Returns (room, room_player) or None.
        """
        try:
            room = GameRoom.objects.get(room_code=self.room_code, status=GameRoom.STATUS_WAITING)
        except GameRoom.DoesNotExist:
            return None

        if user and user.is_authenticated:
            rp = RoomPlayer.objects.filter(
                room=room, user=user, status=RoomPlayer.STATUS_ACTIVE
            ).first()
            return (room, rp) if rp else None
        elif guest_name:
            rp = RoomPlayer.objects.filter(
                room=room, guest_name__iexact=guest_name,
                status=RoomPlayer.STATUS_ACTIVE
            ).first()
            return (room, rp) if rp else None
        return None

    @database_sync_to_async
    def build_room_state(self):
        """Build serializable room state dict."""
        try:
            room = GameRoom.objects.prefetch_related('room_players').get(id=self.room_id)
            players = []
            for rp in room.room_players.filter(status=RoomPlayer.STATUS_ACTIVE):
                players.append({
                    'id': str(rp.id),
                    'display_name': rp.display_name,
                    'is_host': rp.is_host,
                    'is_bot': rp.is_bot,
                    'is_guest': rp.is_guest,
                    'bot_difficulty': rp.bot_difficulty,
                })
            return {
                'room_code': room.room_code,
                'target_score': room.target_score,
                'max_players': room.max_players,
                'current_count': room.current_player_count,
                'can_start': room.can_start,
                'status': room.status,
                'players': players,
            }
        except GameRoom.DoesNotExist:
            return {}

    @database_sync_to_async
    def start_game_db(self):
        try:
            room = GameRoom.objects.get(id=self.room_id)
            for attempt in range(3):
                try:
                    RoomService.start_game(room)
                    room.refresh_from_db()
                    return {'success': True, 'game_id': str(room.game.id)}
                except Exception as e:
                    if attempt == 2:
                        return {'success': False, 'error': str(e)}
        except GameRoom.DoesNotExist:
            return {'success': False, 'error': 'Room not found'}

    @database_sync_to_async
    def add_bot_db(self, difficulty):
        try:
            room = GameRoom.objects.get(id=self.room_id)
            RoomService.add_bot_to_room(room, difficulty)
            return {'success': True}
        except ValueError as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def remove_bot_db(self):
        try:
            room = GameRoom.objects.get(id=self.room_id)
            RoomService.remove_bot_from_room(room)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def leave_room_db(self):
        try:
            rp = RoomPlayer.objects.get(id=self.player_id)
            RoomService.leave_room(rp)
        except RoomPlayer.DoesNotExist:
            pass