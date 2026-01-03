from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import List

from msgspec import to_builtins

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
        n_original_hits = sum(1 for r in self.rolls[:self.original_dice] if r in (5, 6))
        n_original_rerolls = self.original_dice - n_original_hits
        n_current_rerolls = self.dice - self.dice_hits
        post_dice_adjustment = n_current_rerolls - n_original_rerolls
        if post_dice_adjustment < 0:
            line = "".join(emojis[x - 1] for x in self.rerolled_dice[:n_current_rerolls])
            line += "-~~" + "".join(str(x) for x in self.rerolled_dice[n_current_rerolls:n_original_rerolls]) + "~~"
        else:
            line = "".join(emojis[x - 1] for x in self.rerolled_dice[:n_original_rerolls])

        if len(self.rerolled_dice) > n_original_rerolls:
            if post_dice_adjustment > 0:
                line += "+" + "".join(emojis[x - 1] for x in self.rerolled_dice[n_original_rerolls:n_current_rerolls])
            if len(self.rerolled_dice) > n_current_rerolls:
                line += "-~~" + "".join(str(x) for x in self.rerolled_dice[n_current_rerolls:]) + "~~"
        return line

    @staticmethod
    def from_hitsresult(hits_result: HitsResult, rng: random.Random = _default_random):
        rerolls = [rng.randint(1, 6) for _ in range(hits_result.dice - hits_result.dice_hits)]
        new_hits = sum(1 for r in rerolls if r in (5, 6))
        return SecondChanceHitsResult(**to_builtins(hits_result), rerolled_dice=rerolls, rerolled_hits=new_hits)

    def adjust_dice(self, adjustment: int, rng: random.Random = _default_random):
        replacement_base = super().adjust_dice(adjustment, rng)
        added_dice_amount = replacement_base.dice - replacement_base.dice_hits - len(self.rerolled_dice)
        added_rerolls = [rng.randint(1, 6) for _ in range(added_dice_amount)]
        new_rerolled_dice = self.rerolled_dice + added_rerolls
        new_rerolled_hits = sum(
            1 for r in new_rerolled_dice[0:replacement_base.dice - replacement_base.dice_hits] if r in (5, 6))
        return replace(replacement_base, rerolled_dice=new_rerolled_dice, rerolled_hits=new_rerolled_hits)
