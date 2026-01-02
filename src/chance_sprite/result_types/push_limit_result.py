from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from typing import List

from chance_sprite.emojis.emoji_manager import EmojiPacks
from chance_sprite.result_types.additive_result import AdditiveResult
from chance_sprite.result_types.hits_result import HitsResult
from . import _default_random


@dataclass(frozen=True, kw_only=True)
class PushTheLimitHitsResult(HitsResult):
    exploded_dice: List[List[int]]
    rerolled_hits: int

    @property
    def hits_limited(self):
        return self.dice_hits + self.rerolled_hits

    def render_limited_hits(self):
        if self.limit > 0:
            return f" **{self.dice_hits}** hit{'' if self.dice_hits == 1 else 's'} ~~limit {self.limit}~~"
        else:
            return f" **{self.dice_hits}** hit{'' if self.dice_hits == 1 else 's'}"

    def render_roll(self, *, emoji_packs: EmojiPacks):
        line = super().render_roll(emoji_packs=emoji_packs)
        emojis = emoji_packs.d6_ex
        line += f"\n`>push:`" + "".join(emojis[x - 1] for x in self.exploded_dice[0]) + f" **{sum(1 for r in self.exploded_dice[0] if r in (5, 6))}** hits"
        for roll in self.exploded_dice[1:]:
            line += f"\n`explode:`" + "".join(emojis[x - 1] for x in roll) + f" **{sum(1 for r in roll if r in (5, 6))}** hits"
        line += f"\n**{self.hits_limited}** Total Hits"
        return line

    @staticmethod
    def from_hits_result(hits_result: HitsResult, edge: int, rng: random.Random = _default_random):
        explosion_iterations = []
        sixes = edge
        total_hits = 0
        while True:
            rerolls = [rng.randint(1, 6) for _ in range(sixes)]
            explosion_iterations.append(rerolls)
            sixes = sum(1 for r in rerolls if r == 6)
            total_hits += sum(1 for r in rerolls if r in (5, 6))
            if sixes == 0:
                break

        return PushTheLimitHitsResult(**asdict(hits_result), exploded_dice=explosion_iterations, rerolled_hits=total_hits)


def from_hitsresult(hits_result: HitsResult, rng: random.Random = _default_random):
    return AdditiveResult(**asdict(hits_result))