"""
Game constants for Spa card game.
All magic numbers and configuration values live here.
"""

# Suits with Ghanaian names
class Suit:
    YET = "Yet"      # Hearts (Red)
    KALO = "Kalo"    # Diamonds (Red)
    SPA = "Spa"      # Spades (Black)
    CRANE = "Crane"  # Clubs (Black)
    
    ALL = [YET, KALO, SPA, CRANE]
    RED = [YET, KALO]
    BLACK = [SPA, CRANE]


# Card ranks (no Aces, no Jokers)
class Rank:
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    
    ALL = [SIX, SEVEN, EIGHT, NINE, TEN, JACK, QUEEN, KING]
    
    # Numeric value for comparison
    VALUES = {
        SIX: 6,
        SEVEN: 7,
        EIGHT: 8,
        NINE: 9,
        TEN: 10,
        JACK: 11,
        QUEEN: 12,
        KING: 13,
    }


# Game configuration
class GameConfig:
    DECK_SIZE = 32  # 4 suits × 8 ranks
    CARDS_PER_HAND = 5
    ROUNDS_PER_SET = 5
    DEFAULT_TARGET_SCORE = 12
    SCORE_INCREMENT = 6  # When extending game
    MAX_PLAYERS = 4
    MIN_PLAYERS = 2


# Scoring bonuses
class Scoring:
    BASE_WIN = 1
    
    # Last card bonuses
    LAST_SEVEN = 2
    LAST_SIX = 3
    
    # Last two cards bonuses
    LAST_TWO_SEVENS = 4
    LAST_SIX_SEVEN = 5  # Any order
    LAST_TWO_SIXES = 6
    
    # Steal bonus (7 offsets 6 on final card)
    STEAL_BONUS = 1
    
    # Foul penalty
    FOUL_PENALTY = -3
    NON_FOULING_BONUS_2P = 1  # In 2-player, non-fouling gets +1


# Stack configuration
class StackConfig:
    GAUGE_FILL_TIME = 10  # seconds
    MAX_STACK_SIZE = 5  # Can stack up to 5 cards (all remaining rounds)
    ONE_USE_PER_SET = True


# Game status
class GameStatus:
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"


class SetStatus:
    ACTIVE = "active"
    ENDED = "ended"