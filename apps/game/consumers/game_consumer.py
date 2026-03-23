# apps/game/consumers/game_consumer.py

import json
import asyncio
from typing import Dict, Any, Optional
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from apps.game.utils import IDMapper
from apps.game.models import Game, GamePlayer
from apps.game.services import GameService, CardPlayService
from .events import EventBuilder, GameEvent
from apps.bots.tasks import BotTurnHandler


class GameConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for game events.
    
    URL: ws/game/<uuid:game_id>/
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_id = None
        self.game_group_name = None
        self.player_id = None  # This will be a string (UUID)
        self.user = None
        self.id_mapper = None  # Will be set after getting players
    
    async def connect(self):
        """Handle WebSocket connection - supports both authenticated users and guests."""
        print("\n" + "="*60)
        print("WEBSOCKET CONNECTION ATTEMPT")
        print("="*60)
        
        self.user = self.scope['user']
        print(f"1. User authenticated: {self.user.is_authenticated}")
        
        # Get game ID from URL
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        self.game_group_name = f'game_{self.game_id}'
        print(f"2. Game ID from URL: {self.game_id}")
        
        # For guests, get from query string
        query_string = self.scope.get('query_string', b'').decode()
        print(f"3. Raw query string: '{query_string}'")
        
        query_params = {}
        if query_string:
            query_params = dict(param.split('=') for param in query_string.split('&') if param)
            print(f"4. Parsed query params: {query_params}")
        
        guest_name = query_params.get('guest_name')
        print(f"5. Guest name from query: '{guest_name}'")
        
        try:
            # Step 1: Get player
            print("\n--- STEP 1: Getting player ---")
            if self.user.is_authenticated:
                player = await self.get_player_by_user()
            elif guest_name:
                player = await self.get_player_by_guest(guest_name)
            else:
                await self.close(code=4001)
                return
            
            if not player:
                await self.close(code=4003)
                return
            
            self.player_id = str(player.id)
            print(f"✓ Player found: ID={self.player_id}, Name={player.display_name}")
            
            # Step 2: Get game and players using database_sync_to_async
            print("\n--- STEP 2: Getting game and players ---")
            game = await self.get_game()
            print(f"✓ Game found: {game.id}, status: {game.status}")
            
            # Get players using database_sync_to_async
            players = await self.get_game_players()
            print(f"✓ Found {len(players)} players in game")
            
            # Create ID mapper (this is pure Python, no DB calls)
            self.id_mapper = IDMapper(players)
            print(f"✓ IDMapper created")
            
            # Step 3: Join group
            print("\n--- STEP 3: Joining channel group ---")
            await self.channel_layer.group_add(
                self.game_group_name,
                self.channel_name
            )
            print(f"✓ Added to group: {self.game_group_name}")
            
            # Step 4: Accept connection
            print("\n--- STEP 4: Accepting connection ---")
            await self.accept()
            print("✓ WebSocket connection accepted")
            
            # Step 5: Mark as connected
            print("\n--- STEP 5: Marking player as connected ---")
            await self.mark_player_connected(True)
            print("✓ Player marked as connected")
            
            # Step 6: Notify others
            print("\n--- STEP 6: Notifying other players ---")
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'broadcast_event',
                    'event': EventBuilder.player_connected(
                        self.player_id,
                        player.display_name
                    )
                }
            )
            print("✓ Other players notified")
            
            # Step 7: Send game state
            print("\n--- STEP 7: Sending game state ---")
            game_state = await self.get_game_state()
            if game_state.get('current_round'):
                self.current_round_number = game_state['current_round']
            await self.send(text_data=json.dumps(
                EventBuilder.game_state(game_state)
            ))
            print("✓ Game state sent to client")
            
            # Step 8: Start stack gauge (ALWAYS run for testing - works in practice mode too)
            print("\n--- STEP 8: Starting stack gauge ---")
            # Start the gauge as a background task so it doesn't block
            asyncio.create_task(self.start_stack_gauge(reset_first=True))
            print("✓ Stack gauge started")
            
            # Step 9: Check if current player is a bot and trigger their turn
            print("\n--- STEP 9: Checking if bot should play ---")
            current_player_id = game_state.get('current_player_id')
            if current_player_id:
                print(f"Current player to move: {current_player_id}")
                # Check if this player is a bot
                for player in players:
                    if str(player.id) == current_player_id and player.is_bot:
                        print(f"Current player is bot, triggering turn after short delay...")
                        await asyncio.sleep(1.0)
                        await self.trigger_specific_bot_turn(current_player_id)
                        break
                else:
                    print(f"Current player is human - sending your_turn event")
                    await self.channel_layer.group_send(
                        self.game_group_name,
                        {
                            'type': 'broadcast_event',
                            'event': EventBuilder.your_turn(current_player_id)
                        }
                    )
            else:
                print("No current player determined")
            
            print("\n" + "="*60)
            print("CONNECTION SUCCESSFUL")
            print("="*60 + "\n")
            
        except Exception as e:
            print("\n" + "!"*60)
            print(f"ERROR IN CONNECT: {e}")
            import traceback
            traceback.print_exc()
            print("!"*60 + "\n")
            await self.close(code=4004)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if self.game_group_name and self.player_id:
            # Mark player as disconnected
            await self.mark_player_connected(False)
            
            # Notify others - pass string ID
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'broadcast_event',
                    'event': EventBuilder.player_disconnected(self.player_id)
                }
            )
            
            # Leave game group
            await self.channel_layer.group_discard(
                self.game_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'play_card':
                await self.handle_play_card(data)
            
            elif action == 'stack':
                await self.handle_stack(data)
            
            elif action == 'request_state':
                await self.handle_request_state()
            
            else:
                await self.send(text_data=json.dumps(
                    EventBuilder.error(f"Unknown action: {action}", "UNKNOWN_ACTION")
                ))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps(
                EventBuilder.error("Invalid JSON", "INVALID_JSON")
            ))
        except Exception as e:
            print(f"Receive error: {e}")
            await self.send(text_data=json.dumps(
                EventBuilder.error(str(e), "INTERNAL_ERROR")
            ))
    
    async def handle_play_card(self, data: Dict[str, Any]):
        """Handle card play action."""
        card_data = data.get('card')
        
        if not card_data:
            await self.send(text_data=json.dumps(
                EventBuilder.error("Card data required", "MISSING_CARD")
            ))
            return
        
        # Process card play
        success, error, event_data = await self.play_card(card_data)
        
        if not success:
            await self.send(text_data=json.dumps(
                EventBuilder.invalid_play(self.player_id, error)
            ))
            return
        
        # Broadcast card play to all players
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'broadcast_event',
                'event': EventBuilder.card_played(
                    self.player_id,
                    card_data,
                    event_data.get('round_complete', False)
                )
            }
        )
        
        # Handle set end first (takes priority over round completion logic)
        if event_data.get('set_end_results'):
            print("\n=== SET END DETECTED IN CONSUMER ===")
            await self.handle_set_end(event_data['set_end_results'])
            return  # Game may have ended - do not trigger next turn
        
        # Handle round completion events (only if set did NOT end)
        if event_data.get('round_complete'):
            print("\n=== ROUND COMPLETE DETECTED IN CONSUMER ===")
            await self.handle_round_completion(event_data)
        else:
            # Mid-round: check next turn after human play
            await self.check_and_trigger_next_turn()
    

    async def handle_stack(self, data: Dict[str, Any]):
        """
        Handle stack initiation - plays first card immediately, stacks the rest.
        """
        print(f"\n=== HANDLE STACK REQUEST ===")
        cards_data = data.get('cards')
        
        if not cards_data:
            await self.send(text_data=json.dumps(
                EventBuilder.error("Cards data required", "MISSING_CARDS")
            ))
            return
        
        print(f"Player {self.player_id} wants to stack {len(cards_data)} cards")
        
        # Validate and initiate stack (plays first card, stacks the rest)
        success, error, event_data = await self.initiate_stack(cards_data)
        
        if not success:
            print(f"✗ Stack failed: {error}")
            await self.send(text_data=json.dumps(
                EventBuilder.error(error, "STACK_FAILED")
            ))
            return
        
        print(f"✓ Stack initiated successfully")
        print(f"  First card played: {event_data.get('first_card')}")
        print(f"  Cards stacked: {event_data.get('num_cards_stacked', 0)}")
        
        # CRITICAL Step 1: Broadcast the FIRST CARD as a card_played event
        # This lets everyone know a card was played
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'broadcast_event',
                'event': EventBuilder.card_played(
                    self.player_id,
                    event_data.get('first_card'),
                    event_data.get('round_complete', False)
                )
            }
        )
        print("✓ First card played event broadcast")
        
        # Step 2: Broadcast stack initiated event (for the remaining cards)
        if event_data.get('num_cards_stacked', 0) > 0:
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'broadcast_event',
                    'event': EventBuilder.stack_initiated(
                        self.player_id,
                        event_data.get('num_cards_stacked', 0),
                        event_data.get('stacked_cards', [])
                    )
                }
            )
            print(f"✓ Stack initiated event broadcast ({event_data.get('num_cards_stacked', 0)} cards stacked)")
            
            # Step 3: Start gauge animation (non-blocking)
            asyncio.create_task(self.start_stack_gauge(reset_first=True))
            print("✓ Stack gauge animation started (background)")
        
        # Step 4: Handle set end first (takes priority)
        if event_data.get('set_end_results'):
            print("Set ended after stack")
            await self.handle_set_end(event_data['set_end_results'])
            return  # Game may have ended - do not trigger next turn
        
        # Step 5: Handle round completion if needed (only if set did NOT end)
        if event_data.get('round_complete'):
            print("Round complete after stack")
            await self.handle_round_completion(event_data)
        else:
            # Step 6: CRITICAL - Trigger next turn (mid-round only)
            print("Checking next turn after stack...")
            await self.check_and_trigger_next_turn()
        
        print("=== END HANDLE STACK ===\n")
                
    async def start_stack_gauge(self, reset_first=False):
        """
        Start the stack gauge animation for all players.
        If reset_first=True, reset to 0 before starting.
        """
        print("\n=== STACK GAUGE STARTING ===")
        
        if reset_first:
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'broadcast_event',
                    'event': EventBuilder.stack_gauge_update(0, None)
                }
            )
            await asyncio.sleep(0.1)
        
        # Animate from 0 to 100 over 10 seconds
        steps = 20  # Update every 0.5 seconds
        for step in range(steps + 1):
            percentage = int((step / steps) * 100)
            
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'broadcast_event',
                    'event': EventBuilder.stack_gauge_update(percentage, None)
                }
            )
            
            if percentage < 100:
                await asyncio.sleep(0.5)  # 0.5s * 20 = 10 seconds
        
        print("✓ Stack gauge complete")
        print("=== STACK GAUGE END ===\n")
        
    async def reset_stack_gauge(self):
        """Reset the stack gauge to 0."""
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'broadcast_event',
                'event': EventBuilder.stack_gauge_update(0, None)
            }
        )


    async def handle_stack_interrupted_event(self, event):
        """Handle stack interrupted event broadcast."""
        try:
            data = event['event']['data']
            print(f"\n=== STACK INTERRUPTED ===")
            print(f"Stack owned by {data.get('stack_owner_id')} interrupted by {data.get('interrupting_player_id')}")
            # UI will handle showing notification
        except Exception as e:
            print(f"Error in handle_stack_interrupted_event: {e}")


    async def handle_stack_gauge_update(self, event):
        """
        Handle stack gauge update events.
        These are broadcast to all players to animate the gauge.
        """
        try:
            data = event['event']['data']
            percentage = data.get('percentage', 0)
            print(f"📊 Stack gauge update: {percentage}%")
            # The frontend will handle the actual UI update
            # We just need to pass the event through
            pass
        except Exception as e:
            print(f"Error in handle_stack_gauge_update: {e}")
            import traceback
            traceback.print_exc()



    async def handle_request_state(self):
        """Handle state request."""
        game_state = await self.get_game_state()
        await self.send(text_data=json.dumps(
            EventBuilder.game_state(game_state)
        ))
        
    async def handle_card_played_event(self, event):
        """Handle card played event broadcast from others."""
        try:
            data = event['event']['data']
            print(f"\n=== HANDLE CARD PLAYED EVENT ===")
            print(f"Card played data: {data}")
            
            # Just log it - no complex logic needed
            # The process_round_after_bot trigger will handle everything
            pass
                
        except Exception as e:
            print(f"Error in handle_card_played_event: {e}")
            import traceback
            traceback.print_exc()
    
    async def check_and_trigger_next_turn(self):
        """
        Check whose turn it is next and trigger appropriately.
        Also handles auto-playing stacked cards.
        """
        try:
            print("\n=== CHECKING NEXT TURN ===")
            
            # Get fresh game state
            game_state = await self.get_game_state()
            current_player_id = game_state.get('current_player_id')
            
            if not current_player_id:
                print("No current player determined - game may be finished")
                return
            
            # Guard: if game is finished, don't try to determine next player
            if game_state.get('status') == 'finished':
                print("Game is finished - not triggering any turn")
                return
            
            print(f"Next player should be: {current_player_id}")
            
            # Check if current player has a committed stack card to auto-play
            has_stack_card = await self.check_for_auto_play_stack(current_player_id)
            
            if has_stack_card:
                print(f"Player {current_player_id} has committed stack card - auto-playing...")
                await self.auto_play_stack_card(current_player_id)
                return
            
            # No stack card - proceed with normal turn logic
            # Check if this player is a bot or human
            players = await self.get_game_players()
            for player in players:
                if str(player.id) == current_player_id:
                    if player.is_bot:
                        print(f"Next player is bot: {current_player_id}, triggering...")
                        await asyncio.sleep(0.5)
                        await self.trigger_specific_bot_turn(current_player_id)
                    else:
                        print(f"Next player is human: {current_player_id}, sending your_turn event")
                        await self.channel_layer.group_send(
                            self.game_group_name,
                            {
                                'type': 'broadcast_event',
                                'event': EventBuilder.your_turn(current_player_id)
                            }
                        )
                    break
            
            print("=== END TURN CHECK ===\n")
        except Exception as e:
            print(f"Error in check_and_trigger_next_turn: {e}")
            import traceback
            traceback.print_exc()
    
    @database_sync_to_async
    def check_for_auto_play_stack(self, player_id: str) -> bool:
        """
        Check if a player has a committed stack card for the current round.
        
        Args:
            player_id: Player UUID string
        
        Returns:
            True if player has a committed card to auto-play
        """
        try:
            from apps.game.models import Game
            from apps.game.services import SetService
            from apps.game.utils import IDMapper
            from apps.game.engine.stack import StackManager
            
            game = Game.objects.get(id=self.game_id)
            set_obj = game.current_set
            
            if not set_obj:
                return False
            
            # Get players and create ID mapper
            players = list(game.players.all().order_by('seat_position'))
            id_mapper = IDMapper(players)
            
            # Load set state
            set_state = SetService.load_set_state(set_obj, id_mapper)
            
            # Convert player UUID to int
            player_int_id = id_mapper.get_int(player_id)
            if not player_int_id:
                return False
            
            # Check if there's a committed card for this round
            committed_card = StackManager.should_auto_play_from_stack(
                set_state,
                player_int_id,
                set_state.current_round_index
            )
            
            if committed_card:
                print(f"  ✓ Found committed stack card: {committed_card}")
                return True
            
            return False
            
        except Exception as e:
            print(f"Error checking for auto-play: {e}")
            return False
    
    async def auto_play_stack_card(self, player_id: str):
        """
        Automatically play the committed stack card for a player.
        
        Args:
            player_id: Player UUID string
        """
        try:
            print(f"\n=== AUTO-PLAYING STACK CARD ===")
            print(f"Player: {player_id}")
            
            # Get the committed card
            committed_card_dict = await self.get_committed_stack_card(player_id)
            
            if not committed_card_dict:
                print("✗ No committed card found")
                return
            
            print(f"Auto-playing card: {committed_card_dict}")
            
            # Play the card through normal card play service
            success, error, event_data = await self.play_card(committed_card_dict)
            
            if not success:
                print(f"✗ Auto-play failed: {error}")
                return
            
            print("✓ Stack card auto-played successfully")
            
            # Broadcast card play
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'broadcast_event',
                    'event': EventBuilder.card_played(
                        player_id,
                        committed_card_dict,
                        event_data.get('round_complete', False)
                    )
                }
            )
            
            # Handle set end first (takes priority)
            if event_data.get('set_end_results'):
                await self.handle_set_end(event_data['set_end_results'])
                return  # Game may have ended - do not trigger next turn
            
            # Handle round completion if needed (only if set did NOT end)
            if event_data.get('round_complete'):
                await self.handle_round_completion(event_data)
            else:
                # Trigger next turn mid-round
                await self.check_and_trigger_next_turn()
            
            print("=== END AUTO-PLAY ===\n")
            
        except Exception as e:
            print(f"Error in auto_play_stack_card: {e}")
            import traceback
            traceback.print_exc()
    
    @database_sync_to_async
    def get_committed_stack_card(self, player_id: str) -> dict:
        """
        Get the committed stack card for the current round.
        
        Args:
            player_id: Player UUID string
        
        Returns:
            Card dictionary or None
        """
        try:
            from apps.game.models import Game
            from apps.game.services import SetService
            from apps.game.utils import IDMapper
            from apps.game.engine.stack import StackManager
            
            game = Game.objects.get(id=self.game_id)
            set_obj = game.current_set
            
            if not set_obj:
                return None
            
            # Get players and create ID mapper
            players = list(game.players.all().order_by('seat_position'))
            id_mapper = IDMapper(players)
            
            # Load set state
            set_state = SetService.load_set_state(set_obj, id_mapper)
            
            # Convert player UUID to int
            player_int_id = id_mapper.get_int(player_id)
            if not player_int_id:
                return None
            
            # Get committed card
            committed_card = StackManager.should_auto_play_from_stack(
                set_state,
                player_int_id,
                set_state.current_round_index
            )
            
            if committed_card:
                return committed_card.to_dict()
            
            return None
            
        except Exception as e:
            print(f"Error getting committed card: {e}")
            return None
        
    async def process_round_after_bot(self, event):
        """
        Handler called after bot plays and viewing delay completes.
        
        CRITICAL: Only ONE consumer processes to avoid duplicate triggers.
        """
        try:
            # Use cache lock to ensure only one consumer processes
            from django.core.cache import cache
            cache_key = f"bot_processing_lock_{self.game_id}"
            
            acquired_lock = cache.add(cache_key, self.player_id, timeout=3)
            
            if not acquired_lock:
                print(f"\n=== PROCESS ROUND AFTER BOT (Player {self.player_id}) ===")
                print("Another consumer is processing - skipping")
                print("=== END PROCESS ROUND AFTER BOT (SKIPPED) ===\n")
                return
            
            print(f"\n=== PROCESS ROUND AFTER BOT (Player {self.player_id}) ===")
            print(f"✓ Acquired processing lock")
            
            # Small delay to ensure DB is fully updated
            await asyncio.sleep(0.2)
            
            # Broadcast updated game state to all players
            print("Broadcasting game state to all players...")
            await self.broadcast_game_state_to_all()
            print("✓ Game state broadcast complete")
            
            # CRITICAL: Check if we just completed a round
            game_state = await self.get_game_state()
            current_round = game_state.get('current_round', 0)
            played_cards_count = len(game_state.get('played_cards', []))
            
            # If round just started (no cards played yet), wait before triggering bot
            if played_cards_count == 0 and current_round > 0:
                print(f"New round {current_round} just started - adding brief pause...")
                await asyncio.sleep(0.5)  # Brief pause for UI to update
            
            # Now check and trigger next turn
            print("Checking if next player is a bot...")
            await self.check_and_trigger_next_turn()
            
            # Release lock
            cache.delete(cache_key)
            
            print("=== END PROCESS ROUND AFTER BOT ===\n")
            
        except Exception as e:
            print(f"Error processing round after bot: {e}")
            import traceback
            traceback.print_exc()
            
            # Clean up lock
            try:
                from django.core.cache import cache
                cache_key = f"bot_processing_lock_{self.game_id}"
                cache.delete(cache_key)
            except:
                pass
        
    async def bot_turn_complete(self, event):
        """
        Handler called when a bot finishes their turn completely.
        Only ONE consumer should process this.
        """
        try:
            # Use cache lock
            from django.core.cache import cache
            cache_key = f"bot_complete_lock_{self.game_id}"
            
            acquired_lock = cache.add(cache_key, self.player_id, timeout=2)
            
            if not acquired_lock:
                return  # Another consumer is handling it
            
            print(f"\n=== BOT TURN COMPLETE (Consumer {self.player_id}) ===")
            
            # Small delay for DB consistency
            await asyncio.sleep(0.1)
            
            # Get current game state
            game_state = await self.get_game_state()
            current_round = game_state.get('current_round', 0)
            played_cards_count = len(game_state.get('played_cards', []))
            
            # Check if round just completed (no cards in new round)
            if played_cards_count == 0 and current_round > 0:
                print(f"Round completed - broadcasting new round state")
                # Broadcast the new round state
                await self.broadcast_game_state_to_all()
                # Brief pause for frontend to update
                await asyncio.sleep(0.3)
            
            # Check and trigger next turn
            print("Checking next turn...")
            await self.check_and_trigger_next_turn()
            
            # Release lock
            cache.delete(cache_key)
            
            print("=== END BOT TURN COMPLETE ===\n")
            
        except Exception as e:
            print(f"Error in bot_turn_complete: {e}")
            import traceback
            traceback.print_exc()
            
            # Clean up lock
            try:
                from django.core.cache import cache
                cache_key = f"bot_complete_lock_{self.game_id}"
                cache.delete(cache_key)
            except:
                pass


    async def bot_turn_complete(self, event):
        """
        Handler called when a bot finishes their turn completely.
        Only ONE consumer should process this.
        """
        try:
            # Use cache lock
            from django.core.cache import cache
            cache_key = f"bot_complete_lock_{self.game_id}"
            
            acquired_lock = cache.add(cache_key, self.player_id, timeout=2)
            
            if not acquired_lock:
                return  # Another consumer is handling it
            
            print(f"\n=== BOT TURN COMPLETE (Consumer {self.player_id}) ===")
            
            # Small delay for DB consistency
            await asyncio.sleep(0.1)
            
            # Get current game state
            game_state = await self.get_game_state()
            current_round = game_state.get('current_round', 0)
            played_cards_count = len(game_state.get('played_cards', []))
            
            # Check if round just completed (no cards in new round)
            if played_cards_count == 0 and current_round > 0:
                print(f"Round completed - broadcasting new round state")
                # Broadcast the new round state
                await self.broadcast_game_state_to_all()
                # Brief pause for frontend to update
                await asyncio.sleep(0.3)
            
            # Check and trigger next turn
            print("Checking next turn...")
            await self.check_and_trigger_next_turn()
            
            # Release lock
            cache.delete(cache_key)
            
            print("=== END BOT TURN COMPLETE ===\n")
            
        except Exception as e:
            print(f"Error in bot_turn_complete: {e}")
            import traceback
            traceback.print_exc()
            
            # Clean up lock
            try:
                from django.core.cache import cache
                cache_key = f"bot_complete_lock_{self.game_id}"
                cache.delete(cache_key)
            except:
                pass

                                        
    async def broadcast_game_state_to_all(self):
        """
        Broadcast updated game state to ALL players.
        Each player will receive their own personalized version with their hand.
        """
        print("Broadcasting game state to all players...")
        
        # Broadcast to group - each consumer will personalize it
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'send_game_state_to_player',
            }
        )
        print("Game state broadcast initiated")
    
    async def send_game_state_to_player(self, event):
        """
        Handler that sends personalized game state to THIS specific player.
        Called when group receives 'send_game_state_to_player' message.
        """
        try:
            print(f"Sending game state to player {self.player_id}")
            
            # Get game state WITH this player's hand
            game_state = await self.get_game_state()
            
            # Send to this player
            await self.send(text_data=json.dumps(
                EventBuilder.game_state(game_state)
            ))
            
            print(f"✓ Game state sent to player {self.player_id}")
            
        except Exception as e:
            print(f"Error sending game state to player {self.player_id}: {e}")
    
    async def handle_round_completion(self, event_data: Dict[str, Any]):
        """Handle round completion events."""
        try:
            print("\n=== HANDLE ROUND COMPLETION CALLED ===")
            
            # Small delay to ensure database is updated
            await asyncio.sleep(0.5)
            
            # Get and broadcast updated game state
            updated_state = await self.get_game_state()
            print(f"New round index: {updated_state.get('current_round')}")
            print(f"New current player: {updated_state.get('current_player_id')}")
            
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'broadcast_event',
                    'event': EventBuilder.game_state(updated_state)
                }
            )
            
            # Check if this was the last round of the set
            # We can detect this by checking if the new round index is 1 (meaning we just completed round 5)
            # or if the game state shows the set as ended
            current_round = updated_state.get('current_round', 0)
            if current_round == 1 or current_round == 0:
                # This means we either:
                # - Just completed round 5 and are starting round 1 of next set (current_round=1)
                # - The set ended and no new round exists (current_round=0)
                print("🔄 Set transition detected - restarting stack gauge")
                await self.start_stack_gauge(reset_first=True)
            
            # Check next turn for the new round — only if game is still active
            game_check = await self.get_game_state()
            if game_check.get('status') != 'finished':
                await self.check_and_trigger_next_turn()
            else:
                print("Game is finished - skipping next turn trigger")
            
            print("=== END ROUND COMPLETION ===\n")
        except Exception as e:
            print(f"Error in handle_round_completion: {e}")
            import traceback
            traceback.print_exc()
    
    async def trigger_specific_bot_turn(self, bot_player_id: str):
        """
        Trigger a specific bot's turn.
        Uses await to make it blocking - next turn won't trigger until this completes.
        """
        try:
            print(f"Triggering bot: {bot_player_id}")
            
            # Use database_sync_to_async to run bot turn synchronously
            await database_sync_to_async(BotTurnHandler.process_bot_turn)(
                str(self.game_id), 
                bot_player_id
            )
            
        except Exception as e:
            print(f"Bot trigger error: {e}")

    
    async def handle_set_end(self, set_end_results: Dict[str, Any]):
        """Handle set end events."""
        try:
            # Broadcast set end
            scores = await self.get_current_scores()
            
            # Convert integer ID to UUID using IDMapper
            winner_int = set_end_results.get('winner_id')
            winner_uuid = self.id_mapper.get_uuid(winner_int) if winner_int else None
            
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'broadcast_event',
                    'event': EventBuilder.set_ended(
                        winner_uuid,
                        set_end_results.get('score_awarded', 0),
                        scores
                    )
                }
            )
            
            # Check if game ended
            if set_end_results.get('game_ended'):
                game_winner_uuid = set_end_results.get('game_winner_id')
                winner_name = await self.get_player_display_name(game_winner_uuid)
                
                await self.channel_layer.group_send(
                    self.game_group_name,
                    {
                        'type': 'broadcast_event',
                        'event': EventBuilder.game_ended(
                            game_winner_uuid,
                            scores,
                            winner_name
                        )
                    }
                )
        except Exception as e:
            print(f"Error in handle_set_end: {e}")
            import traceback
            traceback.print_exc()
    
    async def broadcast_event(self, event):
        """Broadcast event to WebSocket."""
        try:
            event_data = event['event']
            event_type = event_data.get('type')
            
            print(f"\n=== BROADCAST EVENT: {event_type} ===")
            
            if event_type == GameEvent.CARD_PLAYED:
                await self.handle_card_played_event(event)
            elif event_type == GameEvent.STACK_INTERRUPTED:
                await self.handle_stack_interrupted_event(event)
            elif event_type == GameEvent.STACK_GAUGE_UPDATE:
                await self.handle_stack_gauge_update(event)
            
            await self.send(text_data=json.dumps(event_data))
            
            if event_type == GameEvent.GAME_STATE:
                round_num = event_data.get('data', {}).get('current_round')
                if round_num:
                    self.current_round_number = round_num
                
                await self.check_pending_round_completion()
                await self.check_and_trigger_next_turn()
                
            elif event_type == GameEvent.YOUR_TURN:
                print(f"Your turn for player: {event_data.get('data', {}).get('player_id')}")
                    
        except Exception as e:
            print(f"Error in broadcast_event: {e}")
            import traceback
            traceback.print_exc()
                
    # Database operations (async wrappers)
    
    @database_sync_to_async
    def get_player_by_user(self) -> Optional[GamePlayer]:
        """Get player for authenticated user in this game."""
        try:
            return GamePlayer.objects.select_related('user', 'game').get(
                game_id=self.game_id,
                user=self.user
            )
        except GamePlayer.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_player_by_guest(self, guest_name: str) -> Optional[GamePlayer]:
        """Get player for guest user in this game."""
        try:
            return GamePlayer.objects.select_related('game').get(
                game_id=self.game_id,
                is_guest=True,
                guest_name=guest_name
            )
        except GamePlayer.DoesNotExist:
            return None    
    
    @database_sync_to_async
    def mark_player_connected(self, is_connected: bool):
        """Mark player as connected/disconnected."""
        try:
            player = GamePlayer.objects.get(id=self.player_id)
            player.is_connected = is_connected
            player.save(update_fields=['is_connected', 'last_action_at'])
        except GamePlayer.DoesNotExist:
            pass
        
    @database_sync_to_async
    def get_game_state(self) -> Dict:
        """Get current game state."""
        try:
            game = Game.objects.get(id=self.game_id)
            return GameService.get_game_state(game, for_player_id=self.player_id)
        except Game.DoesNotExist:
            return {}
    
    @database_sync_to_async
    def play_card(self, card_data: Dict):
        """Process card play."""
        try:
            game = Game.objects.get(id=self.game_id)
            player = GamePlayer.objects.get(id=self.player_id)
            return CardPlayService.play_card(game, player, card_data)
        except (Game.DoesNotExist, GamePlayer.DoesNotExist):
            return False, "Game or player not found", None
        except Exception as e:
            print(f"Error in play_card: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e), None



    
    @database_sync_to_async
    def initiate_stack(self, cards_data: list):
        """Process stack initiation."""
        try:
            game = Game.objects.get(id=self.game_id)
            player = GamePlayer.objects.get(id=self.player_id)
            return CardPlayService.initiate_stack(game, player, cards_data)
        except (Game.DoesNotExist, GamePlayer.DoesNotExist):
            return False, "Game or player not found", None
    
    @database_sync_to_async
    def get_current_scores(self) -> Dict[str, int]:
        """Get current scores for all players with string keys."""
        try:
            game = Game.objects.get(id=self.game_id)
            return {
                str(p.id): p.score
                for p in game.players.all()
            }
        except Game.DoesNotExist:
            return {}

    @database_sync_to_async
    def get_player_display_name(self, player_id: str) -> str:
        """Get display name for a player by UUID string."""
        try:
            player = GamePlayer.objects.get(id=player_id)
            return player.display_name
        except GamePlayer.DoesNotExist:
            return 'Unknown'

    async def trigger_next_bot_turn(self):
        """Check if next player is a bot and trigger their turn."""
        try:
            game = await self.get_game()
            set_obj = await self.get_current_set(game)
            
            if not set_obj:
                return
            
            asyncio.create_task(self.process_bot_turn_async(str(game.id)))
        
        except Exception as e:
            print(f"Trigger bot turn error: {e}")
    
    async def process_bot_turn_async(self, game_id: str):
        """Process bot turn asynchronously."""
        try:
            from apps.bots.tasks import BotTurnHandler
            await database_sync_to_async(BotTurnHandler.process_bot_turn)(
                game_id, 
                None
            )
        except Exception as e:
            print(f"Bot turn processing error: {e}")
    
    @database_sync_to_async
    def get_game(self):
        """Get game instance."""
        try:
            print(f"    DB: Fetching game with id={self.game_id}")
            game = Game.objects.get(id=self.game_id)
            print(f"    DB: Game found: {game.id}")
            return game
        except Game.DoesNotExist:
            print(f"    DB: Game {self.game_id} not found")
            raise
        except Exception as e:
            print(f"    DB: Error fetching game: {e}")
            raise

    @database_sync_to_async
    def get_game_players(self):
        """Get all players for the current game."""
        try:
            game = Game.objects.get(id=self.game_id)
            return list(game.players.all().order_by('seat_position'))
        except Game.DoesNotExist:
            return []
    
    @database_sync_to_async
    def get_current_set(self, game):
        """Get current set."""
        return game.current_set