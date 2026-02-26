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
        Process a bot's turn - ONLY plays card and adds viewing delay.
        All broadcasting and state management is handled by the consumer.
        
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
            
            # Bot thinking delay
            thinking_delay = random.uniform(0.5, 1.2)
            print(f"Bot thinking for {thinking_delay:.2f} seconds...")
            time.sleep(thinking_delay)
            
            # Get all players and create ID mapper
            players = list(game.players.all().order_by('seat_position'))
            id_mapper = IDMapper(players)
            
            # Load set state
            set_obj = game.current_set
            if not set_obj:
                print("No active set")
                return
            
            set_state = SetService.load_set_state(set_obj, id_mapper)
            current_round_number = set_state.current_round_index + 1
            
            # Get bot's integer ID
            bot_int_id = id_mapper.get_int_required(str(bot_player.id))
            
            # Create bot instance
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
            
            if not success:
                print(f"Bot card play failed: {error}")
                return
            
            print("✓ Bot card play successful")
            
            # Broadcast card played event immediately
            # This is the ONLY broadcast from bot - consumer handles the rest
            BotTurnHandler._broadcast_event(
                game_id,
                EventBuilder.card_played(
                    str(bot_player.id),
                    card_dict,
                    event_data.get('round_complete', False),
                    current_round_number
                )
            )
            print("✓ Card played event broadcast")
            
            # VIEWING DELAY - let players see the cards on screen
            num_players = len(players)
            viewing_delay = 2.5 if num_players == 2 else 1.5
            
            print(f"Viewing delay ({viewing_delay}s) - cards remain visible...")
            time.sleep(viewing_delay)
            print("✓ Viewing delay complete")
            
            # After viewing delay, trigger consumer to process everything
            print("Triggering consumer to process round completion...")
            BotTurnHandler._trigger_consumer_processing(game_id)
            print("✓ Consumer processing triggered")
            
            print("=== BOT TURN COMPLETE ===\n")
                
        except Exception as e:
            print(f"✗ Bot turn error: {e}")
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
    
    @staticmethod
    def _trigger_consumer_processing(game_id: str):
        """
        Trigger consumer to process round completion and broadcast game state.
        This sends a special message that tells the consumer to handle everything.
        """
        try:
            channel_layer = get_channel_layer()
            group_name = f'game_{game_id}'
            
            # Send trigger to consumer to process the round
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'process_round_after_bot',
                }
            )
        except Exception as e:
            print(f"✗ Trigger consumer error: {e}")