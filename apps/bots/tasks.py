"""
Background tasks for bot actions.
"""
import random
import time
from typing import Optional
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.game.models import Game, GamePlayer
from apps.game.services import GameService, SetService, CardPlayService
from apps.game.consumers.events import EventBuilder
from apps.game.utils import IDMapper
from .services import BotService


class BotTurnHandler:
    """Handles bot turns in games."""
    
    @staticmethod
    def process_bot_turn(game_id: str, bot_player_id: str):
        """
        Process a bot's turn.
        
        Args:
            game_id: Game ID (UUID string)
            bot_player_id: Bot player ID (UUID string)
        """
        print(f"\n=== BOT TURN EXECUTION ===")
        print(f"Game ID: {game_id}")
        print(f"Bot Player ID: {bot_player_id}")
        
        try:
            game = Game.objects.get(id=game_id)
            bot_player = GamePlayer.objects.get(id=bot_player_id)
            
            if not bot_player.is_bot:
                print(f"Player {bot_player_id} is not a bot")
                return
            
            # Small random delay to make bot play feel natural
            delay = random.uniform(1.0, 2.5)
            print(f"Bot thinking for {delay:.2f} seconds...")
            time.sleep(delay)
            
            # Get all players and create ID mapper
            players = list(game.players.all().order_by('seat_position'))
            id_mapper = IDMapper(players)
            
            # Load set state
            set_obj = game.current_set
            if not set_obj:
                print("No active set")
                return
            
            set_state = SetService.load_set_state(set_obj, id_mapper)
            
            # Get bot's integer ID
            bot_int_id = id_mapper.get_int_required(str(bot_player.id))
            
            # Create bot instance and choose card
            bot = BotService.create_bot_instance(bot_player)
            
            # Build game state for bot
            from apps.game.engine.state import GameState, PlayerState
            game_state = GameState(
                game_id=str(game.id),
                target_score=game.target_score,
                lead_player_id=id_mapper.get_int(str(game.current_lead.id)) if game.current_lead else 0,
                status=game.status
            )
            
            for player in players:
                int_id = id_mapper.get_int_required(str(player.id))
                game_state.players[int_id] = PlayerState(
                    player_id=int_id,
                    score=player.score,
                    is_active=player.is_active
                )
            
            # Choose and play card
            card = BotService.get_bot_card_choice(bot, game_state, set_state, id_mapper)
            card_dict = card.to_dict()
            print(f"Bot chose: {card_dict}")
            
            # Execute card play
            success, error, event_data = CardPlayService.play_card(
                game, bot_player, card_dict
            )
            
            if success:
                print("Bot card play successful")
                # Broadcast card play event
                BotTurnHandler._broadcast_event(
                    game_id,
                    EventBuilder.card_played(
                        str(bot_player.id),
                        card_dict,
                        event_data.get('round_complete', False)
                    )
                )
                
                # NO TURN MANAGEMENT HERE - let consumer handle it
            else:
                print(f"Bot card play failed: {error}")
                
        except Exception as e:
            print(f"Bot turn error: {e}")
            import traceback
            traceback.print_exc()
    
    @staticmethod
    def _broadcast_event(game_id: str, event: dict):
        """Broadcast event to game group."""
        try:
            channel_layer = get_channel_layer()
            group_name = f'game_{game_id}'
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'broadcast_event',
                    'event': event
                }
            )
        except Exception as e:
            print(f"Broadcast error: {e}")