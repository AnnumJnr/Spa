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
@permission_classes([AllowAny])
def create_room_view(request):
    """Create a private room - guests and authenticated users."""
    mode = request.data.get('mode', 'private')
    target_score = request.data.get('target_score', 12)
    max_players = request.data.get('max_players', 4)
    bots = request.data.get('bots', [])

    is_guest, user, guest_name = get_or_create_guest_identity(request)

    try:
        if mode == 'practice':
            from apps.game.models import Game
            from apps.game.services import GameService as GS

            players = [{
                'user': user if not is_guest else None,
                'is_guest': is_guest,
                'guest_name': guest_name if is_guest else None,
                'is_bot': False,
            }]
            for bot_config in bots[:3]:
                players.append({
                    'user': None,
                    'is_bot': True,
                    'bot_difficulty': bot_config.get('difficulty', 'intermediate'),
                })

            game = GS.create_game(players=players, target_score=target_score, is_practice=True)
            GS.start_game(game)

            return Response({'success': True, 'game_id': str(game.id)}, status=status.HTTP_201_CREATED)

        # Private room — guests allowed
        room, room_player = RoomService.create_room(
            mode=mode,
            target_score=int(target_score),
            max_players=int(max_players),
            host_user=user if not is_guest else None,
            host_guest_name=guest_name if is_guest else None,
        )

        return Response({
            'room_code': room.room_code,
            'room_id': str(room.id),
            'player_id': str(room_player.id),
        }, status=status.HTTP_201_CREATED)

    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({'error': f'Failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def join_room_view(request, room_code=None, room_id=None):
    """Join a room by room_code. Guests provide guest_name."""
    is_guest, user, guest_name = get_or_create_guest_identity(request)

    # Accept room_code from URL param or body
    code = room_code or request.data.get('room_code', '').strip().upper()
    incoming_guest_name = request.data.get('guest_name', '').strip()

    if is_guest:
        if not incoming_guest_name:
            return Response({'error': 'Guest name is required'}, status=status.HTTP_400_BAD_REQUEST)
        guest_name = incoming_guest_name

    try:
        room = GameRoom.objects.get(room_code=code)
    except GameRoom.DoesNotExist:
        return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)

    if room.status != GameRoom.STATUS_WAITING:
        return Response({'error': 'Room is no longer accepting players'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        room_player = RoomService.join_room(
            room,
            user=user if not is_guest else None,
            guest_name=guest_name if is_guest else None,
        )
        return Response({
            'room_code': room.room_code,
            'room_id': str(room.id),
            'player_id': str(room_player.id),
            'display_name': room_player.display_name,
        })
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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