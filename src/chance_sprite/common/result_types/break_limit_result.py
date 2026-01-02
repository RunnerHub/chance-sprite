from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from typing import List

from chance_sprite.common.common import _default_random, Glitch
from chance_sprite.common.result_types.hits_result import HitsResult
from chance_sprite.emojis.emoji_manager import EmojiPacks


@dataclass(frozen=True, kw_only=True)
class BreakTheLimitHitsResult(HitsResult):
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
        for roll in self.exploded_dice:
            line += f"\n`explode:`" + "".join(emojis[x - 1] for x in roll) + f"**{sum(1 for r in roll if r in (5, 6))}** hits"
        line += f"\n**{self.hits_limited}** Total Hits"
        return line

    @staticmethod
    def roll_exploding(dice: int, *, limit: int = 0, gremlins: int = 0, rng: random.Random = _default_random) -> BreakTheLimitHitsResult:
        rolls = [rng.randint(1, 6) for _ in range(dice)]
        ones = sum(1 for r in rolls if r == 1)
        dice_hits = sum(1 for r in rolls if r in (5, 6))
        exploded_dice = []
        rerolled_hits = 0
        sixes = sum(1 for r in rolls if r==6)
        while True:
            rerolls = [rng.randint(1, 6) for _ in range(sixes)]
            exploded_dice.append(rerolls)
            sixes = sum(1 for r in rerolls if r == 6)
            rerolled_hits += sum(1 for r in rerolls if r in (5, 6))
            if sixes == 0:
                break
        glitch = Glitch.NONE
        if ones * 2 + gremlins > dice:
            glitch = Glitch.CRITICAL if dice_hits == 0 else Glitch.GLITCH
        return BreakTheLimitHitsResult(dice=dice, rolls=rolls, ones=ones, dice_hits=dice_hits, glitch=glitch, limit=limit, gremlins=gremlins, exploded_dice=exploded_dice, rerolled_hits=rerolled_hits)

    @staticmethod
    def from_hitsresult(hits_result: HitsResult, rng: random.Random = _default_random):
        return BreakTheLimitHitsResult(**asdict(hits_result))