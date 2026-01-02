from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from typing import List

from chance_sprite.common.common import _default_random
from chance_sprite.common.result_types.hits_result import HitsResult
from chance_sprite.emojis.emoji_manager import EmojiPacks


@dataclass(frozen=True)
class AdditiveResult:
    dice: int
    rolls: List[int]
    total_roll: int

    @staticmethod
    def roll(dice: int, *, rng: random.Random = _default_random) -> AdditiveResult:
        rolls = [rng.randint(1, 6) for _ in range(dice)]
        total_roll = sum(r for r in rolls)
        return AdditiveResult(dice=dice, rolls=rolls, total_roll=total_roll)

    def render_dice(self, *, emoji_packs: EmojiPacks) -> str:
        emojis = emoji_packs.d6
        line = "".join(emojis[x - 1] for x in self.rolls)
        return line

    @staticmethod
    def from_hitsresult(hits_result: HitsResult, rng: random.Random = _default_random):
        return AdditiveResult(**asdict(hits_result))