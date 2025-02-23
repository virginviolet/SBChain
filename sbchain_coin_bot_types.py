from typing import Dict, TypedDict, List
from discord import PartialEmoji


class BotConfig(TypedDict):
    coin: str
    Coin: str
    coins: str
    Coins: str
    coin_emoji_id: str
    casino_house_id: str
    administrator_id: str


class Reels(TypedDict):
    reel1: dict[str, int]
    reel2: dict[str, int]
    reel3: dict[str, int]


class ReelSymbol(TypedDict):
    emoji_name: str
    emoji_id: int
    fixed_amount: int
    wager_multiplier: float


class ReelResult(TypedDict):
    associated_combo_event: Dict[str, ReelSymbol]
    emoji: PartialEmoji


class ReelResults(TypedDict):
    reel1: ReelResult
    reel2: ReelResult
    reel3: ReelResult


class SpinEmoji(TypedDict):
    emoji_name: str
    emoji_id: int


class SpinEmojis(TypedDict):
    spin1: SpinEmoji
    spin2: SpinEmoji
    spin3: SpinEmoji


class SlotMachineConfig(TypedDict):
    combo_events: dict[str, ReelSymbol]
    reels: Reels
    reel_spin_emojis: SpinEmojis
    fees: dict[str, int | float]
    jackpot_pool: int
    new_bonus_wait_seconds: int


class SaveData(TypedDict):
    user_name: str
    user_id: int
    starting_bonus_available: bool | float
    messages_mined: List[int]
    has_visited_casino: bool
