"""
Card and Deck classes for Spa game.
"""
import random
from typing import List, Optional, Dict, Any
from .constants import Suit, Rank


class Card:
    """Represents a single playing card."""
    
    def __init__(self, suit: str, rank: int | str):
        if suit not in Suit.ALL:
            raise ValueError(f"Invalid suit: {suit}")
        if rank not in Rank.ALL:
            raise ValueError(f"Invalid rank: {rank}")
        
        self.suit = suit
        self.rank = rank
    
    @property
    def value(self) -> int:
        """Get numeric value for comparison."""
        return Rank.VALUES[self.rank]
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.rank == other.rank
    
    def __hash__(self) -> int:
        return hash((self.suit, self.rank))
    
    def __repr__(self) -> str:
        return f"Card({self.rank}{self.suit[0]})"
    
    def __str__(self) -> str:
        return f"{self.rank} of {self.suit}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "suit": self.suit,
            "rank": self.rank,
            "value": self.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Card':
        """Deserialize from dictionary."""
        return cls(suit=data["suit"], rank=data["rank"])
    
    def is_higher_than(self, other: 'Card') -> bool:
        """Check if this card has higher value than another."""
        return self.value > other.value
    
    def same_suit(self, other: 'Card') -> bool:
        """Check if this card has same suit as another."""
        return self.suit == other.suit


class Deck:
    """Represents a deck of 32 Spa cards."""
    
    def __init__(self):
        self.cards: List[Card] = []
        self._build_deck()
    
    def _build_deck(self) -> None:
        """Build a fresh 32-card deck."""
        self.cards = [
            Card(suit, rank)
            for suit in Suit.ALL
            for rank in Rank.ALL
        ]
    
    def shuffle(self) -> None:
        """Shuffle the deck."""
        random.shuffle(self.cards)
    
    def cut(self, index: int) -> None:
        """
        Cut the deck at the specified index.
        Card at index becomes top, cards before it go to bottom.
        """
        if not 0 <= index < len(self.cards):
            raise ValueError(f"Invalid cut index: {index}")
        
        self.cards = self.cards[index:] + self.cards[:index]
    
    def deal(self, num_cards: int) -> List[Card]:
        """
        Deal specified number of cards from top of deck.
        Returns dealt cards and removes them from deck.
        """
        if num_cards > len(self.cards):
            raise ValueError(f"Not enough cards to deal {num_cards}")
        
        dealt = self.cards[:num_cards]
        self.cards = self.cards[num_cards:]
        return dealt
    
    def can_deal_full_hands(self, num_players: int, cards_per_hand: int = 5) -> bool:
        """Check if deck has enough cards for full hands."""
        return len(self.cards) >= (num_players * cards_per_hand)
    
    def reset(self) -> None:
        """Reset deck to fresh state (rebuilt and shuffled)."""
        self._build_deck()
        self.shuffle()
    
    def __len__(self) -> int:
        return len(self.cards)
    
    def __repr__(self) -> str:
        return f"Deck({len(self.cards)} cards)"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize deck to dictionary."""
        return {
            "cards": [card.to_dict() for card in self.cards],
            "count": len(self.cards)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Deck':
        """Deserialize deck from dictionary."""
        deck = cls()
        deck.cards = [Card.from_dict(card_data) for card_data in data["cards"]]
        return deck


class Hand:
    """Represents a player's hand of cards."""
    
    def __init__(self, cards: Optional[List[Card]] = None):
        self.cards: List[Card] = cards or []
    
    def add_cards(self, cards: List[Card]) -> None:
        """Add cards to hand."""
        self.cards.extend(cards)
    
    def remove_card(self, card: Card) -> None:
        """Remove a specific card from hand."""
        if card not in self.cards:
            raise ValueError(f"Card {card} not in hand")
        self.cards.remove(card)
    
    def has_card(self, card: Card) -> bool:
        """Check if hand contains a specific card."""
        return card in self.cards
    
    def has_suit(self, suit: str) -> bool:
        """Check if hand contains any card of the specified suit."""
        return any(card.suit == suit for card in self.cards)
    
    def get_cards_of_suit(self, suit: str) -> List[Card]:
        """Get all cards of a specific suit."""
        return [card for card in self.cards if card.suit == suit]
    
    def clear(self) -> None:
        """Remove all cards from hand."""
        self.cards.clear()
    
    def __len__(self) -> int:
        return len(self.cards)
    
    def __repr__(self) -> str:
        return f"Hand({len(self.cards)} cards)"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize hand to dictionary."""
        return {
            "cards": [card.to_dict() for card in self.cards],
            "count": len(self.cards)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Hand':
        """Deserialize hand from dictionary."""
        cards = [Card.from_dict(card_data) for card_data in data["cards"]]
        return cls(cards)