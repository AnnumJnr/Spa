"""
Pure Python game engine for Spa card game.
Framework-agnostic - can be used with Django, Flask, or standalone.

Public API:
- GameEngine: Main orchestrator
- GameState, SetState, RoundState: State classes
- Card, Deck: Card utilities
"""

from .card import Card, Deck
from .state import GameState, SetState, RoundState
from .validator import CardValidator
from .rules import RuleEngine
from .stack import StackManager
from .scoring import ScoringEngine
from .transitions import TransitionEngine

__all__ = [
    'Card',
    'Deck',
    'GameState',
    'SetState',
    'RoundState',
    'CardValidator',
    'RuleEngine',
    'StackManager',
    'ScoringEngine',
    'TransitionEngine',
]