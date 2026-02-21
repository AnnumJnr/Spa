"""
WebSocket consumer for lobby events.
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
    WebSocket consumer for lobby/room events.
    
    URL: ws/lobby/<mode>/
    OR: ws/lobby/room/<room_id>/
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_id = None
        self.room_group_name = None
        self.user = None
        self.mode = None
        self.countdown_task = None
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope['user']
        
        # Check authentication
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        # Get room ID or mode from URL
        url_kwargs = self.scope['url_route']['kwargs']
        self.room_id = url_kwargs.get('room_id')
        self.mode = url_kwargs.get('mode')
        
        if self.room_id:
            # Joining specific room
            self.room_group_name = f'room_{self.room_id}'
            
            # Verify user is in room
            is_in_room = await self.check_user_in_room()
            if not is_in_room:
                await self.close(code=4003)
                return
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Send current room state
            room_state = await self.get_room_state()
            await self.send(text_data=json.dumps({
                'type': 'room_state',
                'data': room_state
            }))
            
            # Notify others
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_joined',
                    'username': self.user.username
                }
            )
            
            # Check if countdown should start
            room = await self.get_room()
            if room and room.mode == GameRoom.MODE_MULTIPLAYER:
                if not room.countdown_started_at and room.current_player_count >= 2:
                    await self.start_countdown()
        
        else:
            # General lobby connection
            await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if self.countdown_task:
            self.countdown_task.cancel()
        
        if self.room_group_name:
            # Notify others
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_left',
                    'username': self.user.username
                }
            )
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'ready':
                await self.handle_ready()
            
            elif action == 'start_game':
                await self.handle_start_game()
            
            elif action == 'add_bot':
                await self.handle_add_bot(data)
            
            elif action == 'leave':
                await self.handle_leave()
            
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f"Unknown action: {action}"
                }))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': "Invalid JSON"
            }))
        except Exception as e:
            print(f"Receive error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def handle_ready(self):
        """Handle player ready toggle."""
        await self.toggle_ready()
        
        # Broadcast updated room state
        room_state = await self.get_room_state()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'room_update',
                'data': room_state
            }
        )
    
    async def handle_start_game(self):
        """Handle manual game start (private rooms only)."""
        room = await self.get_room()
        
        if not room:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Room not found'
            }))
            return
        
        # Check if user is host
        if room.host_id != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Only host can start the game'
            }))
            return
        
        # Start game
        success = await self.start_game()
        
        if success:
            # Notify all players
            room_state = await self.get_room_state()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_starting',
                    'data': room_state
                }
            )
    
    async def handle_add_bot(self, data):
        """Handle adding a bot to the room."""
        room = await self.get_room()
        
        if not room:
            return
        
        # Check if user is host
        if room.host_id != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Only host can add bots'
            }))
            return
        
        difficulty = data.get('difficulty', 'intermediate')
        await self.add_bot(difficulty)
        
        # Broadcast updated room state
        room_state = await self.get_room_state()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'room_update',
                'data': room_state
            }
        )
    
    async def handle_leave(self):
        """Handle player leaving room."""
        await self.leave_room()
        await self.close()
    
    async def start_countdown(self):
        """Start countdown timer for multiplayer rooms."""
        await self.mark_countdown_started()
        
        # Notify all players countdown started
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'countdown_started',
                'duration': 10
            }
        )
        
        # Start countdown task
        self.countdown_task = asyncio.create_task(self.countdown_timer())
    
    async def countdown_timer(self):
        """Countdown timer task."""
        try:
            for remaining in range(10, 0, -1):
                await asyncio.sleep(1)
                
                # Broadcast countdown update
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'countdown_tick',
                        'remaining': remaining
                    }
                )
            
            # Countdown finished, start game
            await self.start_game()
            
            # Notify all players
            room_state = await self.get_room_state()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_starting',
                    'data': room_state
                }
            )
        
        except asyncio.CancelledError:
            pass
    
    # Event handlers (called by group_send)
    
    async def player_joined(self, event):
        """Broadcast player joined event."""
        await self.send(text_data=json.dumps({
            'type': 'player_joined',
            'username': event['username']
        }))
    
    async def player_left(self, event):
        """Broadcast player left event."""
        await self.send(text_data=json.dumps({
            'type': 'player_left',
            'username': event['username']
        }))
    
    async def room_update(self, event):
        """Broadcast room state update."""
        await self.send(text_data=json.dumps({
            'type': 'room_update',
            'data': event['data']
        }))
    
    async def countdown_started(self, event):
        """Broadcast countdown started."""
        await self.send(text_data=json.dumps({
            'type': 'countdown_started',
            'duration': event['duration']
        }))
    
    async def countdown_tick(self, event):
        """Broadcast countdown tick."""
        await self.send(text_data=json.dumps({
            'type': 'countdown_tick',
            'remaining': event['remaining']
        }))
    
    async def game_starting(self, event):
        """Broadcast game starting."""
        await self.send(text_data=json.dumps({
            'type': 'game_starting',
            'data': event['data']
        }))
    
    # Database operations
    
    @database_sync_to_async
    def check_user_in_room(self) -> bool:
        """Check if user is in the room."""
        try:
            return RoomPlayer.objects.filter(
                room_id=self.room_id,
                user=self.user,
                status=RoomPlayer.STATUS_ACTIVE
            ).exists()
        except:
            return False
    
    @database_sync_to_async
    def get_room(self) -> Optional[GameRoom]:
        """Get room instance."""
        try:
            return GameRoom.objects.get(id=self.room_id)
        except GameRoom.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_room_state(self):
        """Get current room state."""
        try:
            from .serializers import GameRoomSerializer
            room = GameRoom.objects.get(id=self.room_id)
            return GameRoomSerializer(room).data
        except GameRoom.DoesNotExist:
            return {}
    
    @database_sync_to_async
    def toggle_ready(self):
        """Toggle player ready status."""
        try:
            room_player = RoomPlayer.objects.get(
                room_id=self.room_id,
                user=self.user,
                status=RoomPlayer.STATUS_ACTIVE
            )
            room_player.is_ready = not room_player.is_ready
            room_player.save(update_fields=['is_ready'])
        except RoomPlayer.DoesNotExist:
            pass
    
    @database_sync_to_async
    def start_game(self) -> bool:
        """Start the game."""
        try:
            room = GameRoom.objects.get(id=self.room_id)
            RoomService.start_game(room)
            return True
        except Exception as e:
            print(f"Start game error: {e}")
            return False
    
    @database_sync_to_async
    def add_bot(self, difficulty: str):
        """Add bot to room."""
        try:
            room = GameRoom.objects.get(id=self.room_id)
            RoomService.add_bot_to_room(room, difficulty)
        except Exception as e:
            print(f"Add bot error: {e}")
    
    @database_sync_to_async
    def leave_room(self):
        """Leave the room."""
        try:
            room_player = RoomPlayer.objects.get(
                room_id=self.room_id,
                user=self.user,
                status=RoomPlayer.STATUS_ACTIVE
            )
            RoomService.leave_room(room_player)
        except RoomPlayer.DoesNotExist:
            pass
    
    @database_sync_to_async
    def mark_countdown_started(self):
        """Mark countdown as started in database."""
        try:
            room = GameRoom.objects.get(id=self.room_id)
            room.start_countdown()
        except GameRoom.DoesNotExist:
            pass