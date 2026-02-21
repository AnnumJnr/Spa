"""
API views for lobby and matchmaking.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from apps.game.utils import get_or_create_guest_identity
from rest_framework.response import Response
from rest_framework import status

from .models import GameRoom, RoomPlayer
from .services import RoomService, MatchmakingService
from .serializers import GameRoomSerializer, RoomPlayerSerializer


@api_view(['POST'])
@permission_classes([AllowAny])  # ← Changed from IsAuthenticated to AllowAny
def create_room_view(request):
    """Create a new game room - accessible to guests and authenticated users."""
    mode = request.data.get('mode', 'private')
    target_score = request.data.get('target_score', 12)
    max_players = request.data.get('max_players', 4)
    bots = request.data.get('bots', [])  # For practice mode
    
    # Get or create guest identity
    is_guest, user, guest_name = get_or_create_guest_identity(request)
    
    try:
        # For practice mode with bots
# For practice mode with bots
        if mode == 'practice':
            from apps.game.models import Game, GamePlayer
            from apps.game.services import GameService
            
            # Prepare player data
            players = []
            
            # Add human player (guest or authenticated)
            players.append({
                'user': user if not is_guest else None,
                'is_guest': is_guest,
                'guest_name': guest_name if is_guest else None,
                'is_bot': False
            })
            
            # Add bots
            for bot_config in bots[:3]:  # Max 3 bots
                players.append({
                    'user': None,
                    'is_bot': True,
                    'bot_difficulty': bot_config.get('difficulty', 'intermediate')
                })
            
            # Create game using GameService
            game = GameService.create_game(
                players=players,
                target_score=target_score,
                is_practice=True
            )
            
            # Update player guest info for the human player
            if is_guest:
                human_player = game.players.first()
                human_player.is_guest = True
                human_player.guest_name = guest_name
                human_player.save()
            
            # Start the game (this deals cards and initializes first set!)
            GameService.start_game(game)
            
            return Response({
                'success': True,
                'game_id': str(game.id)
            }, status=status.HTTP_201_CREATED)        
        # For non-practice modes (multiplayer rooms)
        # Only authenticated users can create multiplayer rooms
        if is_guest:
            return Response(
                {'error': 'Guests can only play practice mode. Please create an account for multiplayer.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        room = RoomService.create_room(
            host=user,
            mode=mode,
            target_score=target_score,
            max_players=max_players
        )
        
        return Response(
            GameRoomSerializer(room).data,
            status=status.HTTP_201_CREATED
        )
    
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        import traceback
        print(f"Error creating game: {traceback.format_exc()}")  # Debug logging
        return Response(
            {'error': f'Failed to create game: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_room_view(request, room_id):
    """Join an existing room."""
    try:
        room = GameRoom.objects.get(id=room_id)
        room_player = RoomService.join_room(room, request.user)
        
        return Response(RoomPlayerSerializer(room_player).data)
    
    except GameRoom.DoesNotExist:
        return Response(
            {'error': 'Room not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_room_view(request, room_id):
    """Leave a room."""
    try:
        room = GameRoom.objects.get(id=room_id)
        room_player = room.room_players.get(user=request.user, status=RoomPlayer.STATUS_ACTIVE)
        
        RoomService.leave_room(room_player)
        
        return Response({'success': True})
    
    except (GameRoom.DoesNotExist, RoomPlayer.DoesNotExist):
        return Response(
            {'error': 'Room or player not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_room_view(request, room_id):
    """Start a game from a room (private mode only)."""
    try:
        room = GameRoom.objects.get(id=room_id)
        
        # Only host can start
        if room.host != request.user:
            return Response(
                {'error': 'Only host can start the game'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        RoomService.start_game(room)
        
        return Response(GameRoomSerializer(room).data)
    
    except GameRoom.DoesNotExist:
        return Response(
            {'error': 'Room not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
def room_detail_view(request, room_code):
    """Get room details by room code."""
    try:
        room = GameRoom.objects.get(room_code=room_code)
        return Response(GameRoomSerializer(room).data)
    
    except GameRoom.DoesNotExist:
        return Response(
            {'error': 'Room not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enter_matchmaking_view(request):
    """Enter matchmaking queue."""
    mode = request.data.get('mode', 'quick_match')
    target_score = request.data.get('target_score', 12)
    
    entry = MatchmakingService.enter_queue(
        user=request.user,
        mode=mode,
        target_score=target_score
    )
    
    return Response({
        'queue_id': str(entry.id),
        'is_matched': entry.is_matched,
        'room_code': entry.matched_room.room_code if entry.matched_room else None
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_matchmaking_view(request):
    """Leave matchmaking queue."""
    MatchmakingService.leave_queue(request.user)
    return Response({'success': True})