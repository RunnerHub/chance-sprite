from __future__ import annotations

import random
from dataclasses import dataclass, replace
from functools import cached_property

from ..sprite_context import InteractionContext
from ..sprite_utils import Glitch, _default_random, limit_mask


@dataclass(frozen=True, kw_only=True)
class HitsResult:
    original_dice: int
    rolls: tuple[int, ...]
    limit: int
    gremlins: int
    dice_adjustment: int = 0

    @cached_property
    def limit_reached(self):
        return 0 < self.limit <= self.dice_hits

    @cached_property
    def dice(self):
        return self.original_dice + self.dice_adjustment

    @cached_property
    def counted_rolls(self):
        return self.rolls[: self.dice]

    @cached_property
    def dice_hits(self):
        return sum(1 for r in self.counted_rolls if r in (5, 6))

    @cached_property
    def glitch(self) -> Glitch:
        ones = sum(1 for r in self.counted_rolls if r == 1)
        if ones * 2 + self.gremlins * 2 > self.dice:
            return Glitch.CRITICAL if self.dice_hits == 0 else Glitch.GLITCH
        else:
            return Glitch.NONE

    @cached_property
    def hits_limited(self):
        if self.limit > 0:
            return min(self.limit, self.dice_hits)
        else:
            return self.dice_hits

    # === NEW ROLLS ===
    def adjust_dice(self, adjustment: int, rng: random.Random = _default_random):
        new_dice_adjustment: int = max(
            self.dice_adjustment + adjustment, -self.original_dice
        )
        # Only roll new dice if the new adjustment exceeds the total number rolled
        new_dice_to_roll = self.original_dice + new_dice_adjustment - len(self.rolls)
        new_rolls = self.rolls
        if new_dice_to_roll > 0:
            additional_rolls = tuple(rng.randint(1, 6) for _ in range(new_dice_to_roll))
            new_rolls = self.rolls + additional_rolls
        return replace(self, rolls=new_rolls, dice_adjustment=new_dice_adjustment)

    def adjust_limit(self, limit):
        return replace(self, limit=limit)

    # === RENDERING ===
    def render_limited_hits(self):
        if self.limit > 0:
            if self.dice_hits > self.limit:
                return f" ~~{self.dice_hits} hit{'' if self.dice_hits == 1 else 's'}~~ limit **{self.limit}**"
            else:
                return f" **{self.dice_hits}** hit{'' if self.dice_hits == 1 else 's'} ~~limit {self.limit}~~"
        else:
            return f" **{self.dice_hits}** hit{'' if self.dice_hits == 1 else 's'}"

    def render_roll(self, context: InteractionContext):
        line = f"`{self.dice}d6:`" + self.render_dice(context)
        line += self.render_limited_hits()
        return line

    def get_dice_mask(self):
        return limit_mask(self.limit, self.rolls[: self.dice])

    def choose_emojis(self, context: InteractionContext):
        packs = context.emoji_manager.packs
        chosen_emojis = (
            packs.d6
            if (self.glitch == Glitch.NONE)
            else context.emoji_manager.packs.d6_glitch
        )
        limited_emojis = (
            packs.d6_limited
            if (self.glitch == Glitch.NONE)
            else context.emoji_manager.packs.d6_limited_glitch
        )
        return chosen_emojis, limited_emojis

    def render_dice(self, context: InteractionContext) -> str:
        chosen_emojis, limited_emojis = self.choose_emojis(context)

        adjusted_rolls = self.rolls[: self.dice]
        baleeted_dice = self.rolls[self.dice : self.original_dice]
        mask = self.get_dice_mask()

        dice_emojis = [
            chosen_emojis[x - 1] if not mask or mask[i] else limited_emojis[x - 1]
            for (i, x) in enumerate(adjusted_rolls)
        ]

        if self.dice_adjustment < 0:
            line = "".join(dice_emojis)
            line += "-~~" + "".join(str(x) for x in baleeted_dice) + "~~"
        else:
            line = "".join(dice_emojis[: self.original_dice])

        if len(self.rolls) > self.original_dice:
            if self.dice_adjustment > 0:
                line += "+" + "".join(dice_emojis[self.original_dice :])
            if len(self.rolls) > self.dice:
                line += "-~~" + "".join(str(x) for x in self.rolls[self.dice :]) + "~~"
        return line

    def render_glitch(self, context: InteractionContext):
        if self.glitch == Glitch.GLITCH:
            return "```diff\n-Glitch!```"
        if self.glitch == Glitch.CRITICAL:
            return "```diff\n-Critical Glitch!```"
        return ""

    def render_roll_with_glitch(self, context: InteractionContext):
        line = self.render_roll(context)
        line += self.render_glitch(context)
        return line
