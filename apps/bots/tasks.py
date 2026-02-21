"""
Background tasks for bot actions.
"""
import asyncio
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
    def process_bot_turn(game_id: str, bot_player_id: Optional[str] = None):
        """
        Process a bot's turn.
        
        Args:
            game_id: Game ID (UUID string)
            bot_player_id: Bot player ID (UUID string) - if None, will determine next bot
        """
        print(f"\n=== BOT TURN PROCESSING ===")
        print(f"Game ID: {game_id}")
        print(f"Bot Player ID: {bot_player_id}")
        
        try:
            game = Game.objects.get(id=game_id)
            
            # If no specific bot provided, find the next bot whose turn it is
            if not bot_player_id:
                bot_player_id = BotTurnHandler._get_next_bot_player(game)
                if not bot_player_id:
                    print("No bot to play")
                    return
                print(f"Next bot determined: {bot_player_id}")
            
            # Get the bot player
            try:
                bot_player = GamePlayer.objects.get(id=bot_player_id)
            except GamePlayer.DoesNotExist:
                print(f"ERROR: Bot player {bot_player_id} not found in database")
                return
            
            if not bot_player.is_bot:
                print(f"Player {bot_player_id} is not a bot")
                return
            
            print(f"Bot player found: {bot_player.display_name}")
            
            # Load game and set states
            set_obj = game.current_set
            if not set_obj:
                print("No active set")
                return
            
            # Get all players and create ID mapper
            players = list(game.players.all().order_by('seat_position'))
            id_mapper = IDMapper(players)
            
            # Load set state
            set_state = SetService.load_set_state(set_obj, id_mapper)
            
            # Get current round
            current_round = set_state.get_current_round()
            if not current_round:
                print("No active round")
                return
            
           
            # Check if it's actually this bot's turn
            bot_int_id = id_mapper.get_int_required(str(bot_player.id))

            # CRITICAL FIX: Determine turn order starting from lead player
            lead_int_id = current_round.lead_player_id
            played_int_ids = [play.player_id for play in current_round.plays]

            # Build turn order starting from lead (clockwise)
            turn_order = []
            lead_index = set_state.active_players.index(lead_int_id)
            for i in range(len(set_state.active_players)):
                player_index = (lead_index + i) % len(set_state.active_players)
                turn_order.append(set_state.active_players[player_index])

            # Find next player to play
            next_player_int = None
            for int_id in turn_order:
                if int_id not in played_int_ids:
                    next_player_int = int_id
                    break

            if next_player_int != bot_int_id:
                print(f"Not bot's turn. Next player: {next_player_int}, Bot: {bot_int_id}")
                return
            
            print(f"It's bot's turn (int ID: {bot_int_id})")
            
            # Build game state object for bot
            from apps.game.engine.state import GameState, PlayerState
            game_state = GameState(
                game_id=str(game.id),
                target_score=game.target_score,
                lead_player_id=id_mapper.get_int(str(game.current_lead.id)) if game.current_lead else 0,
                status=game.status  # Important: set the status!
            )
            
            for player in players:
                int_id = id_mapper.get_int_required(str(player.id))
                game_state.players[int_id] = PlayerState(
                    player_id=int_id,
                    score=player.score,
                    is_active=player.is_active
                )
            
            # Create bot instance
            bot = BotService.create_bot_instance(bot_player)
            
            # Add thinking delay (humanize)
            delay = random.uniform(1.5, 3.0)
            print(f"Bot thinking for {delay:.2f} seconds...")
            time.sleep(delay)
            
            # Check if bot should stack
            if (set_state.lead_player_id == bot_int_id and 
                bot_int_id not in set_state.stack_used_by):
                
                should_stack = BotService.check_bot_should_stack(
                    bot, game_state, set_state, id_mapper
                )
                
                if should_stack:
                    stack_cards = BotService.get_bot_stack_cards(
                        bot, game_state, set_state, id_mapper
                    )
                    
                    if stack_cards:
                        print(f"Bot stacking {len(stack_cards)} cards")
                        # Convert cards to dict format for service
                        stack_cards_dict = [card.to_dict() for card in stack_cards]
                        
                        # Execute stack
                        success, error, event_data = CardPlayService.initiate_stack(
                            game, bot_player, stack_cards_dict
                        )
                        
                        if success:
                            print("Bot stack successful")
                            # Broadcast stack event
                            BotTurnHandler._broadcast_event(
                                game_id,
                                EventBuilder.stack_initiated(
                                    str(bot_player.id),
                                    len(stack_cards)
                                )
                            )
                        else:
                            print(f"Bot stack failed: {error}")
            
            # Choose and play card (always do this, regardless of stacking)
            print("Bot choosing card...")
            card = BotService.get_bot_card_choice(bot, game_state, set_state, id_mapper)
            card_dict = card.to_dict()
            print(f"Bot chose: {card_dict}")
            
            # Execute card play
            success, error, event_data = CardPlayService.play_card(
                game, bot_player, card_dict
            )
                        
            if success:
                print("Bot card play successful")
                # Broadcast card play event with string ID
                BotTurnHandler._broadcast_event(
                    game_id,
                    EventBuilder.card_played(
                        str(bot_player.id),
                        card_dict,
                        event_data.get('round_complete', False)
                    )
                )
                
                # Handle set end (this is separate from round completion)
                if event_data.get('set_end_results'):
                    print("Set ended")
                    BotTurnHandler._handle_set_end(
                        game_id, event_data['set_end_results'], id_mapper
                    )
                    
                    # Check if next turn is also a bot (after set end, but game not ended)
                    if not event_data['set_end_results'].get('game_ended'):
                        time.sleep(1)
                        BotTurnHandler._check_next_bot_turn(game_id)
                else:
                    # Only check for next bot if round is NOT complete
                    # If round is complete, the consumer will handle it via the broadcast
                    if not event_data.get('round_complete'):
                        print("Round not complete, checking for next bot...")
                        time.sleep(0.5)
                        BotTurnHandler._check_next_bot_turn(game_id)
                    else:
                        # Round complete - do nothing here, consumer will handle it
                        print("Round completed - consumer will handle next steps via broadcast")

        except Exception as e:
            print(f"Bot turn error: {e}")
            import traceback
            traceback.print_exc()
    
    @staticmethod
    def _get_next_bot_player(game) -> Optional[str]:
        """
        Determine which bot should play next.
        Returns the UUID string of the next bot player, or None.
        """
        try:
            set_obj = game.current_set
            if not set_obj:
                return None
            
            # Get all players and create ID mapper
            players = list(game.players.all().order_by('seat_position'))
            id_mapper = IDMapper(players)
            
            set_state = SetService.load_set_state(set_obj, id_mapper)
            current_round = set_state.get_current_round()
            
            if not current_round:
                return None
            
            # Find next player to play
            played_int_ids = [play.player_id for play in current_round.plays]
            for int_id in set_state.active_players:
                if int_id not in played_int_ids:
                    # Convert int ID back to UUID
                    player_uuid = id_mapper.get_uuid(int_id)
                    if player_uuid:
                        # Check if this player is a bot
                        try:
                            player = GamePlayer.objects.get(id=player_uuid)
                            if player.is_bot:
                                return player_uuid
                        except GamePlayer.DoesNotExist:
                            continue
                    break
            
            return None
            
        except Exception as e:
            print(f"Error getting next bot: {e}")
            return None
    
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
    def _handle_set_end(game_id: str, set_end_results: dict, id_mapper: IDMapper):
        """Handle set end events."""
        # Convert integer IDs to strings
        winner_int = set_end_results.get('winner_id')
        winner_uuid = id_mapper.get_uuid(winner_int) if winner_int else None
        game_winner_uuid = set_end_results.get('game_winner_id')  # Should already be UUID
        
        # Broadcast set end
        BotTurnHandler._broadcast_event(
            game_id,
            EventBuilder.set_ended(
                winner_uuid,
                set_end_results.get('score_awarded', 0),
                {}  # Scores will be updated separately
            )
        )
        
        # Check if game ended
        if set_end_results.get('game_ended'):
            BotTurnHandler._broadcast_event(
                game_id,
                EventBuilder.game_ended(
                    game_winner_uuid,
                    {}  # Scores will be updated separately
                )
            )
        
    @staticmethod
    def _check_next_bot_turn(game_id: str):
        """Check if next player is a bot and trigger their turn."""
        try:
            print(f"\n=== CHECKING FOR NEXT BOT ===")
            game = Game.objects.get(id=game_id)
            set_obj = game.current_set
            
            if not set_obj:
                print("No active set")
                return
            
            # Get all players and create ID mapper
            players = list(game.players.all().order_by('seat_position'))
            id_mapper = IDMapper(players)
            
            set_state = SetService.load_set_state(set_obj, id_mapper)
            current_round = set_state.get_current_round()
            
            if not current_round:
                print("No active round")
                return
            
            # Find next player to play - MUST follow turn order from lead
            lead_int_id = current_round.lead_player_id
            played_int_ids = [play.player_id for play in current_round.plays]
            unique_played = list(set(played_int_ids))

            # Build turn order starting from lead (clockwise)
            turn_order = []
            lead_index = set_state.active_players.index(lead_int_id)
            for i in range(len(set_state.active_players)):
                player_index = (lead_index + i) % len(set_state.active_players)
                turn_order.append(set_state.active_players[player_index])

            print(f"Turn order (starting from lead {lead_int_id}): {turn_order}")
            print(f"Unique played players: {unique_played}")

            # Check if all players have played
            if len(unique_played) >= len(set_state.active_players):
                print("All players have played in this round - waiting for round completion")
                return

            # Find next player in turn order who hasn't played
            for int_id in turn_order:
                if int_id not in unique_played:
                    # Convert int ID back to UUID string
                    player_uuid = id_mapper.get_uuid(int_id)
                    print(f"Next player to play: int_id={int_id}, uuid={player_uuid}")
                    
                    if player_uuid:
                        player = GamePlayer.objects.get(id=player_uuid)
                        
                        if player.is_bot:
                            print(f"Next player is a bot: {player_uuid}, triggering turn...")
                            time.sleep(0.2)
                            import threading
                            thread = threading.Thread(
                                target=BotTurnHandler.process_bot_turn,
                                args=(game_id, player_uuid)
                            )
                            thread.daemon = True
                            thread.start()
                        else:
                            print(f"Next player is human: {player_uuid}")
                    else:
                        print(f"Could not find UUID for int_id {int_id}")
                    break
            
            print("=== END BOT CHECK ===\n")
        
        except Exception as e:
            print(f"Check next bot turn error: {e}")
            import traceback
            traceback.print_exc()