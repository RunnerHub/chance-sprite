from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from chance_sprite.emojis.emoji_manager import EmojiPacks
from . import _default_random


@dataclass(frozen=True, kw_only=True)
class AdditiveResult:
    dice: int
    rolls: List[int]

    @property
    def total_roll(self):
        return sum(r for r in self.rolls)

    @staticmethod
    def roll(dice: int, *, rng: random.Random = _default_random) -> AdditiveResult:
        rolls = [rng.randint(1, 6) for _ in range(dice)]
        return AdditiveResult(dice=dice, rolls=rolls)

    def render_dice(self, *, emoji_packs: EmojiPacks) -> str:
        emojis = emoji_packs.d6
        line = "".join(emojis[x - 1] for x in self.rolls)
        return line