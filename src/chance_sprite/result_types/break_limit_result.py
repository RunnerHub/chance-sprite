from __future__ import annotations

import random
from dataclasses import dataclass, replace
from functools import cached_property
from itertools import zip_longest
from typing import Iterable

from chance_sprite.result_types.hits_result import HitsResult
from . import _default_random, Glitch
from ..sprite_context import InteractionContext


@dataclass(frozen=True, kw_only=True)
class BreakTheLimitHitsResult(HitsResult):
    exploded_dice: tuple[tuple[int, ...], ...]

    @cached_property
    def base_sixes(self):
        return sum(1 for r in self.counted_rolls if r == 6)

    @cached_property
    def counted_explosions(self):
        index = 0
        count_this = self.base_sixes
        counts = [count_this]
        while count_this > 0:
            layer = self.exploded_dice[index][:count_this]
            count_this = sum(1 for r in layer if r == 6)
            counts.append(count_this)
            index += 1
        return counts

    @cached_property
    def rerolled_hits(self):
        rerolled_hits = 0
        for (count, line) in zip(self.counted_explosions, self.exploded_dice):
            rerolled_hits += sum(1 for r in line[:count] if r in (5, 6))
        return rerolled_hits

    @cached_property
    def dice_hits(self):
        base_hits = sum(1 for r in self.counted_rolls if r in (5, 6))
        rerolled_hits = self.rerolled_hits
        return base_hits + rerolled_hits

    @cached_property
    def glitch(self) -> Glitch:
        base_ones = sum(1 for r in self.counted_rolls if r == 1)
        rerolled_ones = sum(
            sum(1 for r in line[:count] if r == 1)
            for (count, line) in zip(self.counted_explosions, self.exploded_dice)
        )
        ones = base_ones + rerolled_ones
        if ones * 2 + self.gremlins * 2 > self.dice:
            return Glitch.CRITICAL if self.dice_hits == 0 else Glitch.GLITCH
        else:
            return Glitch.NONE

    @cached_property
    def hits_limited(self):
        return self.dice_hits + self.rerolled_hits

    def render_limited_hits(self):
        if self.limit > 0:
            return f" **{self.dice_hits}** hit{'' if self.dice_hits == 1 else 's'} ~~limit {self.limit}~~"
        else:
            return f" **{self.dice_hits}** hit{'' if self.dice_hits == 1 else 's'}"

    def choose_emojis(self, context: InteractionContext):
        packs = context.emoji_manager.packs
        chosen_emojis = packs.d6_ex if (self.glitch == Glitch.NONE) else context.emoji_manager.packs.d6_ex_glitch
        limited_emojis = chosen_emojis
        return chosen_emojis, limited_emojis

    def render_roll(self, context: InteractionContext):
        (chosen_emojis, _) = self.choose_emojis(context)
        line = f"`{self.dice}d6:`" + self.render_dice(context) + " "
        line += self.render_limited_hits()
        for roll in self.exploded_dice:
            line += f"\n`+`{context.emoji_manager.packs.btl}"
            line += f"" + "".join(
                chosen_emojis[x - 1] for x in roll) + f" **{sum(1 for r in roll if r in (5, 6))}** hits "
        line += f"\n**{self.hits_limited}** Total Hits"
        return line

    def adjust_dice(self, adjustment: int, rng: random.Random = _default_random):
        new_dice_adjustment: int = self.dice_adjustment + adjustment
        # Only roll new dice if the new adjustment exceeds the total number rolled
        new_dice_to_roll = self.original_dice + new_dice_adjustment - len(self.rolls)
        new_rolls = self.rolls
        new_exploded_dice: tuple[tuple[int, ...], ...] = self.exploded_dice
        if new_dice_to_roll > 0:
            additional_rolls = [rng.randint(1, 6) for _ in range(new_dice_to_roll)]
            additional_explosions: list[tuple[int, ...]] = []
            additional_sixes = sum(1 for r in additional_rolls if r == 6)
            while True:
                rerolls = tuple(rng.randint(1, 6) for _ in range(additional_sixes))
                additional_explosions.append(rerolls)
                sixes = sum(1 for r in rerolls if r == 6)
                if sixes == 0:
                    break
            pairs: Iterable[tuple[tuple[int, ...], tuple[int, ...]]] = zip_longest(
                new_exploded_dice, tuple(additional_explosions), fillvalue=tuple()
            )
            new_exploded_dice = tuple(a + b for a, b in pairs)
            new_rolls = self.rolls + tuple(additional_rolls)
        return replace(self, rolls=new_rolls, dice_adjustment=new_dice_adjustment, exploded_dice=new_exploded_dice)
