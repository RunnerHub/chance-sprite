from __future__ import annotations

import random
from dataclasses import dataclass, asdict, replace
from typing import List

from chance_sprite.emojis.emoji_manager import EmojiPacks
from chance_sprite.result_types.hits_result import HitsResult
from . import _default_random


@dataclass(frozen=True, kw_only=True)
class SecondChanceHitsResult(HitsResult):
    rerolled_dice: List[int]
    rerolled_hits: int

    @property
    def hits_limited(self):
        total_hits = self.dice_hits + self.rerolled_hits
        if self.limit > 0:
            return min(self.limit, total_hits)
        else:
            return total_hits

    def render_limited_rerolled_hits(self):
        total_hits = self.dice_hits + self.rerolled_hits
        if self.limit > 0:
            if total_hits > self.limit:
                return f" ~~{total_hits} hit{'' if total_hits == 1 else 's'}~~ limit **{self.limit}**"
            else:
                return f" **{total_hits}** hit{'' if total_hits == 1 else 's'} ~~limit {self.limit}~~"
        else:
            return f" **{total_hits}** hit{'' if total_hits == 1 else 's'}"

    def render_roll(self, *, emoji_packs: EmojiPacks):
        line = super().render_roll(emoji_packs=emoji_packs)
        line += f"\n`>edge:`" + self.render_rerolls(emoji_packs=emoji_packs) + self.render_limited_rerolled_hits()
        return line

    def render_rerolls(self, *, emoji_packs: EmojiPacks) -> str:
        emojis = emoji_packs.d6
        if self.dice_adjustment < 0:
            n_dice = self.dice-self.rerolled_hits
            line = "".join(emojis[x - 1] for x in self.rerolled_dice[0:n_dice])
            line += "**-**~~" + "".join(str(x) for x in self.rerolled_dice[n_dice:]) + "~~"
        elif self.dice_adjustment > 0:
            original_rerolls = sum(1 for r in range(self.original_dice) if r<5)
            line = "".join(emojis[x - 1] for x in self.rerolled_dice[0:original_rerolls])
            line += "**+**" + "".join(emojis[x - 1] for x in self.rerolled_dice[original_rerolls:])
        else:
            line = "".join(emojis[x - 1] for x in self.rerolled_dice)
        return line

    @staticmethod
    def from_hitsresult(hits_result: HitsResult, rng: random.Random = _default_random):
        rerolls = [rng.randint(1, 6) for _ in range(hits_result.dice - hits_result.dice_hits)]
        new_hits = sum(1 for r in rerolls if r in (5, 6))
        return SecondChanceHitsResult(**asdict(hits_result), rerolled_dice=rerolls, rerolled_hits=new_hits)

    def adjust_dice(self, adjustment: int, rng: random.Random = _default_random):
        replacement_base = super().adjust_dice(adjustment, rng)
        new_rerolled_dice_amount = replacement_base.dice - replacement_base.dice_hits - len(self.rerolled_dice)
        added_rerolls = [rng.randint(1, 6) for _ in range(new_rerolled_dice_amount)]
        new_rerolled_dice = self.rerolled_dice + added_rerolls
        new_rerolled_hits = sum(1 for r in new_rerolled_dice[0:new_rerolled_dice_amount-1] if r in (5, 6))
        return replace(replacement_base, rerolled_dice=new_rerolled_dice, rerolled_hits=new_rerolled_hits)
