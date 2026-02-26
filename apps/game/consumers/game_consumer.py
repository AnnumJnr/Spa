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
            await self.send(text_data=json.dumps(
                EventBuilder.game_state(game_state)
            ))
            print("✓ Game state sent to client")
            
            # Step 8: Check if current player is a bot and trigger their turn
            print("\n--- STEP 8: Checking if bot should play ---")
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
        
        # Handle round completion events
        if event_data.get('round_complete'):
            print("\n=== ROUND COMPLETE DETECTED IN CONSUMER ===")
            await self.handle_round_completion(event_data)
        
        # Handle set end
        if event_data.get('set_end_results'):
            print("\n=== SET END DETECTED IN CONSUMER ===")
            await self.handle_set_end(event_data['set_end_results'])
        else:
            # Check next turn after human play (if round not complete)
            if not event_data.get('round_complete'):
                await self.check_and_trigger_next_turn()
    
    async def handle_stack(self, data: Dict[str, Any]):
        """Handle stack initiation."""
        cards_data = data.get('cards')
        
        if not cards_data:
            await self.send(text_data=json.dumps(
                EventBuilder.error("Cards data required", "MISSING_CARDS")
            ))
            return
        
        # Process stack
        success, error, event_data = await self.initiate_stack(cards_data)
        
        if not success:
            await self.send(text_data=json.dumps(
                EventBuilder.error(error, "STACK_FAILED")
            ))
            return
        
        # Broadcast stack to all players - use string ID
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'broadcast_event',
                'event': EventBuilder.stack_initiated(
                    self.player_id,
                    event_data.get('num_cards_stacked', 0)
                )
            }
        )
    
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
        """Check whose turn it is next and trigger appropriately."""
        try:
            print("\n=== CHECKING NEXT TURN ===")
            
            # Get fresh game state
            game_state = await self.get_game_state()
            current_player_id = game_state.get('current_player_id')
            
            if not current_player_id:
                print("No current player determined")
                return
            
            print(f"Next player should be: {current_player_id}")
            
            # Check if this player is a bot
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

    async def process_round_after_bot(self, event):
        """
        Handler called after bot plays and viewing delay completes.
        This processes pending round completions and broadcasts updated game state.
        
        Called when bot sends 'process_round_after_bot' message.
        """
        try:
            print(f"\n=== PROCESS ROUND AFTER BOT (Player {self.player_id}) ===")
            
            # Small delay to ensure DB is fully updated
            await asyncio.sleep(0.2)
            
            # Broadcast updated game state to all players
            print("Broadcasting updated game state to all players...")
            await self.broadcast_game_state_to_all()
            print("✓ Game state broadcast complete")
            
            # Check if next player is a bot
            print("Checking if next player is a bot...")
            await self.check_and_trigger_next_turn()
            
            print("=== END PROCESS ROUND AFTER BOT ===\n")
            
        except Exception as e:
            print(f"Error processing round after bot: {e}")
            import traceback
            traceback.print_exc()
    
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
            
            # Check next turn for the new round
            await self.check_and_trigger_next_turn()
            
            print("=== END ROUND COMPLETION ===\n")
        except Exception as e:
            print(f"Error in handle_round_completion: {e}")
            import traceback
            traceback.print_exc()
    
    async def trigger_specific_bot_turn(self, bot_player_id: str):
        """Trigger a specific bot's turn."""
        try:
            print(f"Triggering specific bot turn: {bot_player_id}")
            asyncio.create_task(self.process_specific_bot_turn_async(str(self.game_id), bot_player_id))
        except Exception as e:
            print(f"Trigger specific bot turn error: {e}")

    async def process_specific_bot_turn_async(self, game_id: str, bot_player_id: str):
        """Process specific bot turn asynchronously."""
        try:
            from apps.bots.tasks import BotTurnHandler
            await database_sync_to_async(BotTurnHandler.process_bot_turn)(
                game_id, 
                bot_player_id
            )
        except Exception as e:
            print(f"Specific bot turn processing error: {e}")    
    
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
                
                await self.channel_layer.group_send(
                    self.game_group_name,
                    {
                        'type': 'broadcast_event',
                        'event': EventBuilder.game_ended(
                            game_winner_uuid,
                            scores
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
            
            await self.send(text_data=json.dumps(event_data))
            
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