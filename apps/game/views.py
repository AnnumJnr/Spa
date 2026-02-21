"""
API views for game actions.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Game, GamePlayer
from .services import GameService, CardPlayService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def game_state_view(request, game_id):
    """Get current game state."""
    try:
        game = Game.objects.get(id=game_id)
        
        # Get player if user is in game
        player = game.players.filter(user=request.user).first()
        player_id = int(player.id) if player else None
        
        game_state = GameService.get_game_state(game, for_player_id=player_id)
        
        return Response(game_state)
    
    except Game.DoesNotExist:
        return Response(
            {'error': 'Game not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def play_card_view(request, game_id):
    """Play a card."""
    try:
        game = Game.objects.get(id=game_id)
        player = game.players.get(user=request.user)
        
        card_data = request.data.get('card')
        if not card_data:
            return Response(
                {'error': 'Card data required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success, error, event_data = CardPlayService.play_card(
            game, player, card_data
        )
        
        if not success:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(event_data)
    
    except (Game.DoesNotExist, GamePlayer.DoesNotExist):
        return Response(
            {'error': 'Game or player not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stack_view(request, game_id):
    """Initiate stacking."""
    try:
        game = Game.objects.get(id=game_id)
        player = game.players.get(user=request.user)
        
        cards_data = request.data.get('cards')
        if not cards_data:
            return Response(
                {'error': 'Cards data required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success, error, event_data = CardPlayService.initiate_stack(
            game, player, cards_data
        )
        
        if not success:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(event_data)
    
    except (Game.DoesNotExist, GamePlayer.DoesNotExist):
        return Response(
            {'error': 'Game or player not found'},
            status=status.HTTP_404_NOT_FOUND
        )