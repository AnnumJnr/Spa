"""
Base bot class - abstract interface for all bots.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from apps.game.engine.card import Card
from apps.game.engine.state import GameState, SetState


class BaseBot(ABC):
    """
    Abstract base class for bot players.
    All bots must implement these methods.
    """
    
    def __init__(self, player_id: int, difficulty: str):
        """
        Initialize bot.
        
        Args:
            player_id: Bot's player ID in the game
            difficulty: Difficulty level
        """
        self.player_id = player_id
        self.difficulty = difficulty
        self.cards_seen = []  # Track cards played
        self.suit_counts = {}  # Track suit distribution
    
    @abstractmethod
    def choose_card(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> Card:
        """
        Choose a card to play.
        
        Args:
            game_state: Current game state
            set_state: Current set state
            hand: Bot's current hand
        
        Returns:
            Card to play
        """
        pass
    
    @abstractmethod
    def should_stack(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> bool:
        """
        Decide whether to initiate stacking.
        
        Args:
            game_state: Current game state
            set_state: Current set state
            hand: Bot's current hand
        
        Returns:
            True if should stack, False otherwise
        """
        pass
    
    @abstractmethod
    def choose_stack_cards(
        self,
        game_state: GameState,
        set_state: SetState,
        hand: List[Card]
    ) -> List[Card]:
        """
        Choose cards to stack.
        
        Args:
            game_state: Current game state
            set_state: Current set state
            hand: Bot's current hand
        
        Returns:
            List of cards to stack
        """
        pass
    
    def update_card_memory(self, card: Card):
        """
        Update bot's memory of played cards.
        
        Args:
            card: Card that was played
        """
        self.cards_seen.append(card)
        
        # Update suit counts
        if card.suit not in self.suit_counts:
            self.suit_counts[card.suit] = 0
        self.suit_counts[card.suit] += 1
    
    def get_valid_cards(
        self,
        hand: List[Card],
        lead_suit: Optional[str]
    ) -> List[Card]:
        """
        Get list of valid cards that can be played.
        
        Args:
            hand: Bot's hand
            lead_suit: Current lead suit (None if bot is leading)
        
        Returns:
            List of valid cards
        """
        if lead_suit is None:
            # Bot is leading, all cards valid
            return hand.copy()
        
        # Check if bot has lead suit
        lead_suit_cards = [c for c in hand if c.suit == lead_suit]
        
        if lead_suit_cards:
            # Must follow suit
            return lead_suit_cards
        else:
            # Can play any card
            return hand.copy()
    
    def get_current_lead_card(self, set_state: SetState) -> Optional[Card]:
        """
        Get the current leading card in the round.
        
        Args:
            set_state: Current set state
        
        Returns:
            Current lead card or None
        """
        current_round = set_state.get_current_round()
        if not current_round or not current_round.plays:
            return None
        
        # Find highest card of lead suit
        lead_card = None
        lead_suit = current_round.lead_suit
        
        for play in current_round.plays:
            # FIX: Use object notation instead of dictionary access
            card = play.card  # Changed from play['card']
            if card.suit == lead_suit:
                if lead_card is None or card.value > lead_card.value:
                    lead_card = card
        
        return lead_card
    
    def can_offset_current_lead(
        self,
        hand: List[Card],
        current_lead_card: Optional[Card]
    ) -> List[Card]:
        """
        Get cards that can offset the current lead.
        
        Args:
            hand: Bot's hand
            current_lead_card: Current lead card
        
        Returns:
            List of cards that can offset
        """
        if not current_lead_card:
            return []
        
        offsetting_cards = []
        for card in hand:
            if (card.suit == current_lead_card.suit and 
                card.value > current_lead_card.value):
                offsetting_cards.append(card)
        
        return offsetting_cards
    
    def calculate_remaining_cards_of_suit(self, suit: str) -> int:
        """
        Calculate how many cards of a suit remain in play.
        
        Args:
            suit: Suit to check
        
        Returns:
            Estimated number of remaining cards
        """
        # 8 cards per suit in deck
        seen = self.suit_counts.get(suit, 0)
        return max(0, 8 - seen)