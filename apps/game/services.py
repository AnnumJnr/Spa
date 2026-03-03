"""
Game orchestration services.
Bridge between Django models and pure game engine.
"""
import json
from typing import Optional, Dict, List, Tuple
from django.db import transaction
from django.utils import timezone

from .models import Game, GamePlayer, Set
from .engine.card import Card, Deck, Hand
from .engine.state import GameState, SetState, RoundState, PlayerState, StackState
from .engine.validator import CardValidator
from .engine.rules import RuleEngine
from .engine.stack import StackManager
from .engine.scoring import ScoringEngine
from .engine.transitions import TransitionEngine
from .engine.constants import GameStatus, SetStatus, GameConfig
from .utils import IDMapper


class GameService:
    """Service for game lifecycle management."""
    
    @staticmethod
    @transaction.atomic
    def create_game(
        players: List[Dict],
        target_score: int = GameConfig.DEFAULT_TARGET_SCORE,
        is_practice: bool = False
    ) -> Game:
        """
        Create a new game with players.
        
        Args:
            players: List of player dictionaries
            target_score: Target score to win
            is_practice: Whether this is a practice game
        
        Returns:
            Created Game instance
        """
        # Create game
        game = Game.objects.create(
            target_score=target_score,
            is_practice=is_practice,
            status=GameStatus.WAITING
        )
        
        # Create players with seat positions
        game_players = []
        for idx, player_data in enumerate(players):
            game_player = GamePlayer.objects.create(
                game=game,
                user=player_data.get('user'),
                is_bot=player_data.get('is_bot', False),
                bot_difficulty=player_data.get('bot_difficulty'),
                is_guest=player_data.get('is_guest', False),
                guest_name=player_data.get('guest_name'),
                seat_position=idx,
                score=0,
                is_active=True
            )
            game_players.append(game_player)
        
        # Don't store turn_order in game model - derive it from seat_position
        # turn_order will be computed dynamically when needed
        
        # Initialize deck
        deck = Deck()
        deck.shuffle()
        game.deck_state = deck.to_dict()
        
        game.save()
        
        return game
    
    @staticmethod
    @transaction.atomic
    def start_game(game: Game) -> Game:
        """
        Start a game and initialize first set.
        
        Args:
            game: Game to start
        
        Returns:
            Updated Game instance
        """
        if game.status != GameStatus.WAITING:
            raise ValueError("Game already started")
        
        # Select random lead for first set
        import random
        players_list = list(game.players.all())
        
        # FOR PRACTICE MODE: Always make the human player the first lead
        if game.is_practice:
            # Find the human player (non-bot)
            human_player = None
            for player in players_list:
                if not player.is_bot:
                    human_player = player
                    break
            
            if human_player:
                first_lead = human_player
                print(f"Practice mode - human player {human_player.id} is first lead")
            else:
                # Fallback to random if no human found (shouldn't happen)
                first_lead = random.choice(players_list)
                print(f"No human found, random lead: {first_lead.id}")
        else:
            # Competitive mode - random lead
            first_lead = random.choice(players_list)
            print(f"Competitive mode - random lead: {first_lead.id}")
        
        game.current_lead = first_lead
        game.status = GameStatus.ACTIVE
        game.started_at = timezone.now()
        game.save()
        
        # Create first set
        SetService.create_set(game, set_number=1)
        
        return game
    
    @staticmethod
    def get_game_state(game: Game, for_player_id: Optional[str] = None) -> Dict:
        """
        Get serialized game state.
        
        Args:
            game: Game instance
            for_player_id: Player UUID string. If provided, includes hand for this player
        
        Returns:
            Game state dictionary with UUID strings as player IDs
        """
        # Get all players ordered by seat
        players = list(game.players.all().order_by('seat_position'))
        
        # Create ID mapper
        id_mapper = IDMapper(players)
        
        # Build player list for frontend (with UUID strings)
        players_data = []
        for player in players:
            player_data = {
                'id': str(player.id),  # UUID string
                'name': player.display_name,
                'display_name': player.display_name,
                'score': player.score,
                'is_active': player.is_active,
                'is_connected': player.is_connected,
                'is_bot': player.is_bot,
                'card_count': 0,  # Will be updated from set state
                'has_used_stack': False,  # Will be updated from set state
            }
            players_data.append(player_data)
        
        state_dict = {
            'game_id': str(game.id),
            'target_score': game.target_score,
            'status': game.status,
            'players': players_data,
            'current_lead_id': str(game.current_lead.id) if game.current_lead else None
        }
        
        # Add current set data if exists
        if game.current_set:
            set_state = SetService.load_set_state(game.current_set, id_mapper)
            
            # Update card counts and stack usage
            for player_data in players_data:
                player_uuid = player_data['id']
                int_id = id_mapper.get_int(player_uuid)
                if int_id and int_id in set_state.hands:
                    player_data['card_count'] = len(set_state.hands[int_id].cards)
                # Check if player has used stack this set
                if int_id and int_id in set_state.stack_used_by:
                    player_data['has_used_stack'] = True
            
            # Add stack state to game state for UI
            if set_state.stack_state:
                state_dict['stack'] = {
                    'owner_id': id_mapper.get_uuid(set_state.stack_state.owner_player_id),
                    'stacked_cards': [card.to_dict() for card in set_state.stack_state.stacked_cards],
                    'start_round': set_state.stack_state.start_round_index + 1,
                    'interrupted': set_state.stack_state.interrupted,
                    'interruption_round': set_state.stack_state.interruption_round + 1 if set_state.stack_state.interruption_round is not None else None
                }
            
            # Add current round info
            state_dict['current_round'] = set_state.current_round_index + 1
            state_dict['total_rounds'] = 5
            
            # Get current round
            current_round = set_state.get_current_round()
            
            # Determine whose turn it is (UUID string)
            if current_round:
                # Get who has already played
                played_int_ids = [play.player_id for play in current_round.plays]
                
                # CRITICAL FIX: Determine turn order starting from lead player
                # Turn order must be: lead player first, then clockwise
                lead_int_id = current_round.lead_player_id
                
                # Build turn order starting from lead (clockwise)
                turn_order = []
                lead_index = set_state.active_players.index(lead_int_id)
                
                # Start from lead and go clockwise through active players
                for i in range(len(set_state.active_players)):
                    player_index = (lead_index + i) % len(set_state.active_players)
                    turn_order.append(set_state.active_players[player_index])
                
                # Find next player to play (first in turn order who hasn't played)
                for int_id in turn_order:
                    if int_id not in played_int_ids:
                        current_player_uuid = id_mapper.get_uuid(int_id)
                        if current_player_uuid:
                            state_dict['current_player_id'] = current_player_uuid
                        break
            
            # Add played cards (convert int IDs to UUID strings)
            if current_round:
                played_cards = []
                for play in current_round.plays:
                    player_uuid = id_mapper.get_uuid(play.player_id)
                    if player_uuid:
                        played_cards.append({
                            'player_id': player_uuid,  # UUID string
                            'card': play.card.to_dict()
                        })
                state_dict['played_cards'] = played_cards
            else:
                state_dict['played_cards'] = []
            
            # Add player-specific hand if requested
            if for_player_id:
                int_id = id_mapper.get_int(for_player_id)
                if int_id and int_id in set_state.hands:
                    hand = set_state.hands[int_id]
                    state_dict['hand'] = [card.to_dict() for card in hand.cards]
                else:
                    state_dict['hand'] = []
        else:
            state_dict['hand'] = []
            state_dict['played_cards'] = []
            state_dict['current_round'] = 0
        
        return state_dict
    
    @staticmethod
    @transaction.atomic
    def end_game(game: Game, winner: GamePlayer) -> Game:
        """
        End a game and record results.
        
        Args:
            game: Game to end
            winner: Winning player
        
        Returns:
            Updated Game instance
        """
        game.status = GameStatus.FINISHED
        game.winner = winner
        game.finished_at = timezone.now()
        game.save()
        
        # Create game history if competitive
        if not game.is_practice:
            from .models import GameHistory
            
            duration = None
            if game.started_at and game.finished_at:
                duration = int((game.finished_at - game.started_at).total_seconds())
            
            GameHistory.objects.create(
                game=game,
                winner=winner.user if winner.user else None,
                participants=[p.user.id for p in game.players.all() if p.user],
                final_scores={
                    str(p.user.id): p.score 
                    for p in game.players.all() if p.user
                },
                total_sets=game.sets.count(),
                total_rounds=sum(s.current_round_index for s in game.sets.all()),
                duration_seconds=duration
            )
        
        return game


class SetService:
    """Service for set management."""
    
    @staticmethod
    @transaction.atomic
    def create_set(game: Game, set_number: int) -> Set:
        """
        Create and initialize a new set.
        
        Args:
            game: Parent game
            set_number: Set number (1, 2, 3, ...)
        
        Returns:
            Created Set instance
        """
        # Get players and create ID mapper
        players = list(game.players.all().order_by('seat_position'))
        id_mapper = IDMapper(players)
        
        # Load deck from game
        deck = Deck.from_dict(game.deck_state)
        
        # Check if we need to reshuffle
        num_players = len(players)
        if not deck.can_deal_full_hands(num_players, GameConfig.CARDS_PER_HAND):
            deck.reset()
            game.deck_state = deck.to_dict()
            game.save()
        
        # Deal hands - store with UUID string keys for database
        hands = {}
        for player in players:
            cards = deck.deal(GameConfig.CARDS_PER_HAND)
            hands[str(player.id)] = [card.to_dict() for card in cards]
        
        # Save remaining deck
        game.deck_state = deck.to_dict()
        game.save()
        
        # Get active players (UUID strings)
        active_player_uuids = [
            str(p.id) for p in game.players.filter(is_active=True)
        ]
        
        # Create set
        set_obj = Set.objects.create(
            game=game,
            set_number=set_number,
            status=SetStatus.ACTIVE,
            lead_player=game.current_lead,
            hands=hands,
            active_players=active_player_uuids,
            current_round_index=0,
            rounds=[],
            stack_state=None,
            stack_used_by=[]
        )
        
        # Create first round with integer ID for engine
        lead_int_id = id_mapper.get_int(str(game.current_lead.id))
        if lead_int_id is None:
            print(f"ERROR: Could not map lead player {game.current_lead.id} to int ID")
            active_player_ints = []
            for uuid_str in active_player_uuids:
                int_id = id_mapper.get_int(uuid_str)
                if int_id is not None:
                    active_player_ints.append(int_id)
            lead_int_id = active_player_ints[0] if active_player_ints else 1
            print(f"Using fallback lead ID: {lead_int_id}")

        print(f"Creating round 0 with lead player {lead_int_id}")
        first_round = {
            'round_index': 0,
            'lead_player_id': lead_int_id,
            'lead_suit': None,
            'plays': [],
            'resolved': False
        }
        set_obj.rounds = [first_round]
        set_obj.save()
        
        return set_obj
    
    @staticmethod
    def load_set_state(set_obj: Set, id_mapper: IDMapper) -> SetState:
        """
        Load SetState from database Set model.
        Converts UUID strings to integer IDs for game engine.
        
        Args:
            set_obj: Set model instance
            id_mapper: ID mapper for UUID <-> int conversion
        
        Returns:
            SetState instance with integer player IDs
        """
        # Load hands - convert UUID keys to integer keys
        hands = {}
        for player_uuid_str, cards_data in set_obj.hands.items():
            cards = [Card.from_dict(cd) for cd in cards_data]
            int_id = id_mapper.get_int(player_uuid_str)
            if int_id:
                hands[int_id] = Hand(cards)
        
        # Load rounds - FIXED: No duplicate appending
        rounds = []
        for round_data in set_obj.rounds:
            # Create round state from dictionary
            round_state = RoundState(
                round_index=round_data['round_index'],
                lead_player_id=round_data['lead_player_id'],
                lead_suit=round_data.get('lead_suit'),
                resolved=round_data.get('resolved', False)
            )
            
            # Load plays
            for play in round_data.get('plays', []):
                card = Card.from_dict(play['card'])
                round_state.add_play(play['player_id'], card)
            
            rounds.append(round_state)  # Append only once!
        
        # Load stack state - FIXED: Handle both formats
        stack_state = None
        if set_obj.stack_state:
            stack_data = set_obj.stack_state
            stacked_cards = []
            
            # Try to get stacked_cards from the new format
            if 'stacked_cards' in stack_data:
                stacked_cards = [Card.from_dict(cd) for cd in stack_data.get('stacked_cards', [])]
            # Fall back to old format with committed_cards
            elif 'committed_cards' in stack_data:
                committed_cards = {}
                for pid_key, cards_data in stack_data.get('committed_cards', {}).items():
                    cards = [Card.from_dict(cd) for cd in cards_data]
                    committed_cards[int(pid_key)] = cards
                # Flatten committed_cards to stacked_cards
                for cards in committed_cards.values():
                    stacked_cards.extend(cards)
            
            # Get owner ID - try both possible keys
            owner_id = None
            if 'owner_player_id' in stack_data:
                owner_id = int(stack_data['owner_player_id'])
            elif 'owner_id' in stack_data:
                owner_id = int(stack_data['owner_id'])
            
            if owner_id and stacked_cards:
                stack_state = StackState(
                    owner_player_id=owner_id,
                    stacked_cards=stacked_cards,
                    start_round_index=stack_data.get('start_round_index', 0),
                    interrupted=stack_data.get('interrupted', False),
                    interruption_round=stack_data.get('interruption_round')
                )
        
        # Convert active players from UUID strings to integers
        active_players = []
        for uuid_str in set_obj.active_players:
            int_id = id_mapper.get_int(uuid_str)
            if int_id:
                active_players.append(int_id)
        
        # Convert stack_used_by from UUID strings to integers
        stack_used_by = []
        for uuid_str in set_obj.stack_used_by:
            int_id = id_mapper.get_int(uuid_str)
            if int_id:
                stack_used_by.append(int_id)
        
        # Get lead player as integer
        lead_int_id = id_mapper.get_int_required(str(set_obj.lead_player.id))
        
        # Create set state with integer IDs
        set_state = SetState(
            set_id=str(set_obj.id),
            hands=hands,
            active_players=active_players,
            current_round_index=set_obj.current_round_index,
            lead_player_id=lead_int_id,
            rounds=rounds,  # Now contains only one copy of each round
            stack_state=stack_state,
            stack_used_by=stack_used_by
        )
        
        return set_state
    
    @staticmethod
    @transaction.atomic
    def save_set_state(set_obj: Set, set_state: SetState, id_mapper: IDMapper) -> None:
        """
        Save SetState back to database Set model.
        Converts integer IDs back to UUID strings for storage.
        
        Args:
            set_obj: Set model instance
            set_state: SetState instance with integer player IDs
            id_mapper: ID mapper for UUID <-> int conversion
        """
        # Save hands - convert integer keys back to UUID strings
        hands = {}
        for int_id, hand in set_state.hands.items():
            uuid_str = id_mapper.get_uuid(int_id)
            if uuid_str:
                hands[uuid_str] = [card.to_dict() for card in hand.cards]
        set_obj.hands = hands
        
        # Save rounds (keep integer IDs in round data for engine)
        rounds = []
        for round_state in set_state.rounds:
            round_data = round_state.to_dict()
            rounds.append(round_data)
        set_obj.rounds = rounds
        
        # Save stack state (keep integer IDs)
        if set_state.stack_state:
            stack = set_state.stack_state
            
            # FIX: Use stacked_cards instead of committed_cards
            # Create a dictionary with the stack owner's cards for backward compatibility
            stacked_cards_dict = {
                str(stack.owner_player_id): [card.to_dict() for card in stack.stacked_cards]
            }
            
            set_obj.stack_state = {
                'owner_id': str(stack.owner_player_id),
                'owner_player_id': str(stack.owner_player_id),  # Add both for compatibility
                'num_cards': len(stack.stacked_cards),
                'stacked_cards': [card.to_dict() for card in stack.stacked_cards],  # Main storage
                'committed_cards': stacked_cards_dict,  # Keep for backward compatibility
                'start_round_index': stack.start_round_index,
                'interrupted': stack.interrupted,
                'interruption_round': stack.interruption_round
            }
        else:
            set_obj.stack_state = None
        
        # Convert active players back to UUID strings
        active_player_uuids = []
        for int_id in set_state.active_players:
            uuid_str = id_mapper.get_uuid(int_id)
            if uuid_str:
                active_player_uuids.append(uuid_str)
        set_obj.active_players = active_player_uuids
        
        set_obj.current_round_index = set_state.current_round_index
        
        # Convert stack_used_by back to UUID strings
        stack_used_by_uuids = []
        for int_id in set_state.stack_used_by:
            uuid_str = id_mapper.get_uuid(int_id)
            if uuid_str:
                stack_used_by_uuids.append(uuid_str)
        set_obj.stack_used_by = stack_used_by_uuids
        
        set_obj.save()
            
    @staticmethod
    @transaction.atomic
    def end_set(
        game: Game,
        set_obj: Set,
        set_state: SetState,
        id_mapper: IDMapper
    ) -> Dict:
        """
        End a set and award points.
        
        Args:
            game: Game instance
            set_obj: Set instance
            set_state: Current set state with integer IDs
            id_mapper: ID mapper
        
        Returns:
            Results dictionary with UUID strings for player IDs
        """
        # Build game state for scoring (with integer IDs)
        game_state = GameState(
            game_id=str(game.id),
            target_score=game.target_score,
            status=game.status
        )
        
        players = list(game.players.all().order_by('seat_position'))
        for player in players:
            int_id = id_mapper.get_int_required(str(player.id))
            game_state.players[int_id] = PlayerState(
                player_id=int_id,
                score=player.score,
                is_active=player.is_active
            )
        
        # Determine winner (returns integer ID)
        winner_int_id = TransitionEngine.determine_set_winner(set_state)
        
        # SAFETY CHECK: Ensure winner ID is valid
        if winner_int_id is None or winner_int_id == 0:
            print(f"ERROR: Invalid winner ID {winner_int_id}, using first active player")
            active_players = set_state.active_players
            winner_int_id = active_players[0] if active_players else 1
            print(f"Fallback winner ID: {winner_int_id}")
        
        try:
            winner_uuid = id_mapper.get_uuid_required(winner_int_id)
            winner = GamePlayer.objects.get(id=winner_uuid)
            print(f"Winner found: {winner_uuid}")
        except (KeyError, GamePlayer.DoesNotExist) as e:
            print(f"ERROR mapping winner ID {winner_int_id}: {e}")
            # Fallback to first player
            winner = game.players.first()
            winner_int_id = id_mapper.get_int_required(str(winner.id))
            winner_uuid = str(winner.id)
            print(f"Fallback winner: {winner_uuid}")
        
        # Calculate score
        score_awarded = ScoringEngine.calculate_set_score(
            game_state,
            set_state,
            winner_int_id
        )
        print(f"Score awarded: {score_awarded}")
        
        # Check for steal bonus
        if set_state.rounds:
            final_round = set_state.rounds[-1]
            steal_bonus = ScoringEngine.check_steal_bonus(
                set_state,
                final_round,
                winner_int_id
            )
            if steal_bonus:
                print(f"Steal bonus: {steal_bonus}")
                score_awarded += steal_bonus
        
        # Update winner's score
        winner.score += score_awarded
        winner.save()
        print(f"Winner new score: {winner.score}")
        
        # Update set
        set_obj.status = SetStatus.ENDED
        set_obj.winner = winner
        set_obj.score_awarded = score_awarded
        set_obj.completed_at = timezone.now()
        set_obj.save()
        
        # Clear any active stack at end of set
        StackManager.clear_stack(set_state)
        
        # Check win condition
        game_winner_uuid = None
        game_ended = False
        
        if winner.score >= game.target_score:
            game_ended = True
            game_winner_uuid = str(winner.id)
            print(f"Game ended! Winner: {game_winner_uuid}")
            GameService.end_game(game, winner)
        else:
            # Rotate lead for next set
            print("Rotating lead for next set...")
            new_lead_int_id = TransitionEngine.rotate_lead_for_new_set(game_state)
            print(f"New lead int ID from rotation: {new_lead_int_id}")
            
            # SAFETY CHECK: Ensure we have a valid lead ID
            if new_lead_int_id == 0 or new_lead_int_id is None:
                print(f"ERROR: Invalid lead ID {new_lead_int_id} for next set, using winner")
                new_lead_int_id = winner_int_id
            
            try:
                new_lead_uuid = id_mapper.get_uuid_required(new_lead_int_id)
                new_lead = GamePlayer.objects.get(id=new_lead_uuid)
                game.current_lead = new_lead
                game.save()
                print(f"New lead for next set: {new_lead_uuid}")
            except (KeyError, GamePlayer.DoesNotExist) as e:
                print(f"ERROR setting new lead: {e}, using winner as lead")
                game.current_lead = winner
                game.save()
            
            # Create next set
            print(f"Creating next set: {set_obj.set_number + 1}")
            SetService.create_set(game, set_number=set_obj.set_number + 1)
        
        print("=== END SET ===\n")
        
        # Return with UUID strings
        return {
            'winner_id': winner_int_id,
            'score_awarded': score_awarded,
            'game_ended': game_ended,
            'game_winner_id': game_winner_uuid
        }


class CardPlayService:
    """Service for handling card plays."""
    
    @staticmethod
    @transaction.atomic
    def play_card(
        game: Game,
        player: GamePlayer,
        card_dict: Dict
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Process a card play.
        Now includes auto-play from stack.
        """
        print("\n" + "="*60)
        print("CARD PLAY ATTEMPT")
        print("="*60)
        print(f"1. Game ID from DB: {game.id}")
        print(f"2. Game status from DB: {game.status}")
        print(f"3. Player ID: {player.id}")
        print(f"4. Card data: {card_dict}")
        
        # Get current set
        set_obj = game.current_set
        if not set_obj:
            print("5. ❌ No active set")
            return False, "No active set", None
        
        print(f"5. Set ID: {set_obj.id}")
        print(f"6. Set status from DB: {set_obj.status}")
        
        # Create ID mapper
        players = list(game.players.all().order_by('seat_position'))
        id_mapper = IDMapper(players)
        
        # Load states
        set_state = SetService.load_set_state(set_obj, id_mapper)
        print(f"7. Set state status after load: {set_state.status}")
        
        # Build game state with integer IDs
        game_state_obj = GameState(
            game_id=str(game.id),
            target_score=game.target_score,
            lead_player_id=id_mapper.get_int_required(str(game.current_lead.id)),
            status=game.status
        )
        print(f"8. Game state status before adding players: {game_state_obj.status}")
        
        for p in players:
            int_id = id_mapper.get_int_required(str(p.id))
            game_state_obj.players[int_id] = PlayerState(
                player_id=int_id,
                score=p.score,
                is_active=p.is_active
            )
        
        print(f"9. Game state status after adding players: {game_state_obj.status}")
        
        # Create card object
        card = Card(suit=card_dict['suit'], rank=card_dict['rank'])
        player_int_id = id_mapper.get_int_required(str(player.id))
        print(f"10. Player integer ID: {player_int_id}")
        
        # CHECK FOR AUTO-PLAY FROM STACK
        committed_card = StackManager.should_auto_play_from_stack(
            set_state,
            player_int_id,
            set_state.current_round_index
        )
        
        if committed_card:
            card = committed_card
            print(f"11. ⭐ Auto-playing committed stack card: {card}")
            # Override the card_dict for event data
            card_dict = card.to_dict()
        
        # Get current round
        current_round = set_state.get_current_round()
        if not current_round:
            return False, "No active round", None
        
        # IMPORTANT: Check if player has already played in this round
        if current_round.has_played(player_int_id):
            print(f"⚠️ Player {player_int_id} has already played in this round - preventing duplicate")
            return False, "Player has already played this round", None
        
        # Validate card play
        print("12. Calling validator...")
        is_valid, error = CardValidator.validate_card_play(
            game_state_obj,
            set_state,
            player_int_id,
            card
        )
        
        if not is_valid:
            print(f"13. ❌ Validation failed: {error}")
            return False, error, None
        
        print("13. ✓ Validation passed")
        
        print(f"14. Current round index: {current_round.round_index}")
        print(f"15. Current round lead: {current_round.lead_player_id}")
        print(f"16. Current round plays so far: {len(current_round.plays)}")
        
        # Add play to round
        current_round.add_play(player_int_id, card)
        print(f"17. Added play. Now {len(current_round.plays)} plays in round")
        
        # Remove card from hand (if it's not already removed by stack)
        hand = set_state.hands.get(player_int_id)
        if hand and hand.has_card(card):
            hand.remove_card(card)
            print(f"18. Removed card from hand. {len(hand.cards)} cards remaining")
        
        # Save state
        SetService.save_set_state(set_obj, set_state, id_mapper)
        print("19. State saved to database")
        
        # Check if all active players have played - use unique player IDs
        played_player_ids = set(play.player_id for play in current_round.plays)
        all_played = len(played_player_ids) == len(set_state.active_players)
        print(f"20. Unique players who have played: {played_player_ids}")
        print(f"21. All played? {all_played} ({len(played_player_ids)} of {len(set_state.active_players)})")
        
        event_data = {
            'player_id': player_int_id,
            'card': card.to_dict(),
            'round_complete': all_played
        }
        
        # Process round completion if all played
        if all_played:
            print("22. ALL PLAYERS HAVE PLAYED - Processing round completion")
            results = TransitionEngine.process_round_completion(
                game_state_obj,
                set_state,
                current_round
            )
            
            # Update game lead
            new_lead_uuid = id_mapper.get_uuid_required(game_state_obj.lead_player_id)
            game.current_lead = GamePlayer.objects.get(id=new_lead_uuid)
            game.save()
            
            # Save updated state
            SetService.save_set_state(set_obj, set_state, id_mapper)
            
            # Update player scores in DB if fouls occurred
            if results['fouls'] and results['fouls'].has_fouls():
                for foul_int_id in results['fouls'].fouling_players:
                    foul_uuid = id_mapper.get_uuid_required(foul_int_id)
                    foul_player = GamePlayer.objects.get(id=foul_uuid)
                    foul_player_state = game_state_obj.players[foul_int_id]
                    foul_player.score = foul_player_state.score
                    foul_player.is_active = foul_player_state.is_active
                    foul_player.save()
            
            event_data['results'] = {
                'fouls': results['fouls'].to_dict() if results['fouls'] else None,
                'offset': results['offset'].to_dict() if results['offset'] else None,
                'set_ended': results['set_ended'],
                'round_advanced': results.get('round_advanced', False)
            }
            
            # Handle set end
            if results['set_ended']:
                print("23. SET ENDED")
                end_results = SetService.end_set(game, set_obj, set_state, id_mapper)
                event_data['set_end_results'] = end_results
            
            print("24. Round processing complete")
        else:
            print("22. Round not yet complete")
        
        print("="*60 + "\n")
        return True, None, event_data
    
    @staticmethod
    @transaction.atomic
    def initiate_stack(game: Game, player: GamePlayer, cards_data: list) -> tuple:
        """
        Initiate stacking for a player.
        The first card is played immediately, remaining cards are stacked for future rounds.
        
        Args:
            game: Game instance
            player: Player initiating stack
            cards_data: List of card dictionaries to stack (in play order)
        
        Returns:
            (success, error_message, event_data)
        """
        print(f"\n{'='*60}")
        print(f"STACK INITIATION")
        print(f"{'='*60}")
        print(f"Player: {player.display_name} ({player.id})")
        print(f"Cards to stack: {len(cards_data)}")
        
        try:
            # Get current set
            set_obj = game.current_set
            if not set_obj:
                return False, "No active set", None
            
            # Get all players and create ID mapper
            players = list(game.players.all().order_by('seat_position'))
            id_mapper = IDMapper(players)
            
            # Load set state
            set_state = SetService.load_set_state(set_obj, id_mapper)
            
            # Convert player UUID to integer
            player_int_id = id_mapper.get_int_required(str(player.id))
            
            # Convert card data to Card objects
            from apps.game.engine.card import Card
            cards = [Card.from_dict(card_dict) for card_dict in cards_data]
            
            # Validate stack
            from apps.game.engine.validator import CardValidator
            can_stack, error = CardValidator.can_stack(None, set_state, player_int_id)
            if not can_stack:
                print(f"✗ Cannot stack: {error}")
                return False, error, None
            
            valid, error = CardValidator.validate_stack_cards(set_state, player_int_id, cards)
            if not valid:
                print(f"✗ Invalid stack cards: {error}")
                return False, error, None
            
            # CRITICAL: Take the first card and play it immediately in the current round
            first_card = cards[0]
            remaining_cards = cards[1:] if len(cards) > 1 else []
            
            print(f"  First card '{first_card}' will be played immediately")
            if remaining_cards:
                print(f"  Remaining {len(remaining_cards)} cards will be stacked")
            
            # Get current round
            current_round = set_state.get_current_round()
            if not current_round:
                return False, "No active round", None
            
            # Check if player has already played this round
            if current_round.has_played(player_int_id):
                print(f"⚠️ Player {player_int_id} has already played in this round")
                return False, "Player has already played this round", None
            
            # Validate the first card play
            game_state_obj = GameState(
                game_id=str(game.id),
                target_score=game.target_score,
                lead_player_id=id_mapper.get_int_required(str(game.current_lead.id)),
                status=game.status
            )
            
            for p in players:
                p_int_id = id_mapper.get_int_required(str(p.id))
                game_state_obj.players[p_int_id] = PlayerState(
                    player_id=p_int_id,
                    score=p.score,
                    is_active=p.is_active
                )
            
            is_valid, error = CardValidator.validate_card_play(
                game_state_obj,
                set_state,
                player_int_id,
                first_card
            )
            
            if not is_valid:
                print(f"✗ First card validation failed: {error}")
                return False, error, None
            
            # Add the first card to current round
            current_round.add_play(player_int_id, first_card)
            print(f"  ✓ First card added to current round")
            
            # Remove first card from hand (already will be removed by stack, but we do it explicitly)
            hand = set_state.hands.get(player_int_id)
            if hand and hand.has_card(first_card):
                hand.remove_card(first_card)
            
            # If there are remaining cards, stack them for future rounds
            if remaining_cards:
                from apps.game.engine.stack import StackManager
                stack_state = StackManager.initiate_stack(set_state, player_int_id, remaining_cards)
                print(f"  ✓ Stack initiated with {len(remaining_cards)} cards starting round {stack_state.start_round_index}")
            else:
                # No remaining cards, just mark player as used stack
                set_state.stack_used_by.append(player_int_id)
                print(f"  ✓ Player marked as used stack (no cards remaining)")
            
            # Save state
            SetService.save_set_state(set_obj, set_state, id_mapper)
            print(f"✓ Set state saved")
            
            # Check if all players have played in this round
            played_player_ids = set(play.player_id for play in current_round.plays)
            all_played = len(played_player_ids) == len(set_state.active_players)
            
            # Prepare event data for broadcasting
            event_data = {
                'player_id': str(player.id),
                'first_card': first_card.to_dict(),
                'num_cards_stacked': len(remaining_cards),
                'stacked_cards': [card.to_dict() for card in remaining_cards],
                'round_complete': all_played
            }
            
            print(f"{'='*60}\n")
            
            # If round is now complete, process round completion
            if all_played:
                print("Round complete after stack - processing round completion")
                from apps.game.services import CardPlayService
                # This is a bit recursive, but we need to trigger round completion
                # You might want to call process_round_completion directly here
                results = TransitionEngine.process_round_completion(
                    game_state_obj,
                    set_state,
                    current_round
                )
                
                # Update game lead
                new_lead_uuid = id_mapper.get_uuid_required(game_state_obj.lead_player_id)
                game.current_lead = GamePlayer.objects.get(id=new_lead_uuid)
                game.save()
                
                # Save updated state
                SetService.save_set_state(set_obj, set_state, id_mapper)
                
                event_data['results'] = {
                    'fouls': results['fouls'].to_dict() if results['fouls'] else None,
                    'offset': results['offset'].to_dict() if results['offset'] else None,
                    'set_ended': results['set_ended'],
                    'round_advanced': results.get('round_advanced', False)
                }
                
                # Handle set end
                if results['set_ended']:
                    print("SET ENDED")
                    end_results = SetService.end_set(game, set_obj, set_state, id_mapper)
                    event_data['set_end_results'] = end_results
            
            return True, None, event_data
            
        except Exception as e:
            print(f"✗ Stack initiation error: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e), None
                    
        except Exception as e:
            print(f"✗ Stack initiation error: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e), None