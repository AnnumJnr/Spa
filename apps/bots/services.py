"""
Bot services for game integration.
"""
from typing import Dict, Type
from apps.game.models import GamePlayer
from apps.game.engine.state import GameState, SetState
from apps.game.engine.card import Card
from apps.game.utils import IDMapper  # Add this import
from .engine.base_bot import BaseBot
from .engine.beginner import BeginnerBot
from .engine.intermediate import IntermediateBot
from .engine.advanced import AdvancedBot
from .engine.expert import ExpertBot


class BotService:
    """Service for bot AI operations."""
    
    # Map difficulty to bot class
    BOT_CLASSES: Dict[str, Type[BaseBot]] = {
        'beginner': BeginnerBot,
        'intermediate': IntermediateBot,
        'advanced': AdvancedBot,
        'expert': ExpertBot,
    }
    
    @staticmethod
    def create_bot_instance(player: GamePlayer) -> BaseBot:
        """
        Create a bot instance for a bot player.
        
        Args:
            player: Bot GamePlayer instance
        
        Returns:
            Bot instance
        """
        if not player.is_bot:
            raise ValueError("Player is not a bot")
        
        bot_class = BotService.BOT_CLASSES.get(
            player.bot_difficulty,
            IntermediateBot
        )
        
        # Store the UUID as string, not as int
        return bot_class(
            player_id=str(player.id),  # Keep as UUID string
            difficulty=player.bot_difficulty
        )
    
    @staticmethod
    def get_bot_card_choice(
        bot: BaseBot,
        game_state: GameState,
        set_state: SetState,
        id_mapper: IDMapper  # Add this parameter
    ) -> Card:
        """
        Get bot's card choice.
        
        Args:
            bot: Bot instance
            game_state: Current game state
            set_state: Current set state
            id_mapper: ID mapper for UUID <-> int conversion
        
        Returns:
            Card to play
        """
        # Convert bot's UUID to integer ID using mapper
        bot_int_id = id_mapper.get_int(bot.player_id)
        if not bot_int_id:
            print(f"ERROR: Could not find integer ID for bot UUID {bot.player_id}")
            print(f"Available mappings: {id_mapper.uuid_to_int}")
            raise ValueError(f"Bot has no hand - cannot map UUID {bot.player_id} to int ID")
        
        # Get bot's hand using the integer ID
        hand_obj = set_state.hands.get(bot_int_id)
        if not hand_obj:
            print(f"ERROR: Bot hand not found for int ID {bot_int_id}")
            print(f"Available hands: {list(set_state.hands.keys())}")
            raise ValueError(f"Bot has no hand (int ID: {bot_int_id})")
        
        hand_cards = hand_obj.cards
        print(f"Bot hand has {len(hand_cards)} cards")
        
        return bot.choose_card(game_state, set_state, hand_cards)
    
    @staticmethod
    def check_bot_should_stack(
        bot: BaseBot,
        game_state: GameState,
        set_state: SetState,
        id_mapper: IDMapper  # Add this parameter
    ) -> bool:
        """
        Check if bot should stack.
        
        Args:
            bot: Bot instance
            game_state: Current game state
            set_state: Current set state
            id_mapper: ID mapper for UUID <-> int conversion
        
        Returns:
            True if bot wants to stack
        """
        # Convert bot's UUID to integer ID using mapper
        bot_int_id = id_mapper.get_int(bot.player_id)
        if not bot_int_id:
            return False
        
        hand_obj = set_state.hands.get(bot_int_id)
        if not hand_obj:
            return False
        
        hand_cards = hand_obj.cards
        
        return bot.should_stack(game_state, set_state, hand_cards)
    
    @staticmethod
    def get_bot_stack_cards(
        bot: BaseBot,
        game_state: GameState,
        set_state: SetState,
        id_mapper: IDMapper  # Add this parameter
    ) -> list:
        """
        Get bot's stack card choices.
        
        Args:
            bot: Bot instance
            game_state: Current game state
            set_state: Current set state
            id_mapper: ID mapper for UUID <-> int conversion
        
        Returns:
            List of cards to stack (as dicts)
        """
        # Convert bot's UUID to integer ID using mapper
        bot_int_id = id_mapper.get_int(bot.player_id)
        if not bot_int_id:
            return []
        
        hand_obj = set_state.hands.get(bot_int_id)
        if not hand_obj:
            return []
        
        hand_cards = hand_obj.cards
        
        stack_cards = bot.choose_stack_cards(game_state, set_state, hand_cards)
        
        return [card.to_dict() for card in stack_cards]