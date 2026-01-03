from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import List

from chance_sprite.emojis.emoji_manager import EmojiPacks
from chance_sprite.result_types import Glitch
from . import _default_random


@dataclass(frozen=True, kw_only=True)
class HitsResult:
    original_dice: int
    rolls: List[int]
    limit: int
    gremlins: int
    dice_adjustment: int = 0

    @property
    def dice(self):
        return self.original_dice + self.dice_adjustment

    @property
    def counted_rolls(self):
        return self.rolls[:self.dice]

    @property
    def dice_hits(self):
        return sum(1 for r in self.counted_rolls if r in (5, 6))

    @property
    def glitch(self) -> Glitch:
        ones = sum(1 for r in self.counted_rolls if r == 1)
        if ones * 2 + self.gremlins * 2 > self.dice:
            return Glitch.CRITICAL if self.dice_hits == 0 else Glitch.GLITCH
        else:
            return Glitch.NONE

    @property
    def hits_limited(self):
        if self.limit > 0:
            return min(self.limit, self.dice_hits)
        else:
            return self.dice_hits

    # === NEW ROLLS ===
    @staticmethod
    def roll(dice: int, *, limit: int = 0, gremlins: int = 0, rng: random.Random = _default_random) -> HitsResult:
        rolls = [rng.randint(1, 6) for _ in range(dice)]
        return HitsResult(original_dice=dice, rolls=rolls, limit=limit, gremlins=gremlins)


    def adjust_dice(self, adjustment: int, rng: random.Random = _default_random):
        new_dice_adjustment: int = max(self.dice_adjustment + adjustment, -self.original_dice)
        # Only roll new dice if the new adjustment exceeds the total number rolled
        new_dice_to_roll = self.original_dice + new_dice_adjustment - len(self.rolls)
        new_rolls = self.rolls
        if new_dice_to_roll > 0:
            additional_rolls = [rng.randint(1, 6) for _ in range(new_dice_to_roll)]
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

    def render_roll(self, *, emoji_packs: EmojiPacks):
        line = f"`{self.dice}d6:`" + self.render_dice(emoji_packs=emoji_packs)
        line += self.render_limited_hits()
        return line

    def render_dice(self, *, emoji_packs: EmojiPacks) -> str:
        emojis =  emoji_packs.d6

        if self.dice_adjustment < 0:
            line = "".join(emojis[x - 1] for x in self.rolls[:self.dice])
            line += "-~~" + "".join(str(x) for x in self.rolls[self.dice:self.original_dice]) + "~~"
        else:
            line = "".join(emojis[x - 1] for x in self.rolls[:self.original_dice])

        if len(self.rolls) > self.original_dice:
            if self.dice_adjustment > 0:
                line += "+" + "".join(emojis[x - 1] for x in self.rolls[self.original_dice:self.dice])
            if len(self.rolls) > self.dice:
                line += "-~~" + "".join(str(x) for x in self.rolls[self.dice:]) + "~~"
        return line

    def render_glitch(self, *, emoji_packs: EmojiPacks):
        if self.glitch == Glitch.GLITCH:
            return "```diff\n-Glitch!```"
        if self.glitch == Glitch.CRITICAL:
            return "```diff\n-Critical Glitch!```"
        return ""

    def render_roll_with_glitch(self, *, emoji_packs: EmojiPacks):
        line = self.render_roll(emoji_packs=emoji_packs)
        line += self.render_glitch(emoji_packs=emoji_packs)
        return line
