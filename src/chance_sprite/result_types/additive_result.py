from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from functools import cached_property
from typing import List

from chance_sprite.emojis.emoji_manager import EmojiPacks
from chance_sprite.result_types.hits_result import HitsResult
from . import _default_random


@dataclass(frozen=True)
class AdditiveResult:
    dice: int
    rolls: List[int]

    @cached_property
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

    @staticmethod
    def from_hitsresult(hits_result: HitsResult, rng: random.Random = _default_random):
        return AdditiveResult(**asdict(hits_result))