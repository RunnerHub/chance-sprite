from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import List

from chance_sprite.common.common import Glitch, _default_random
from chance_sprite.emojis.emoji_manager import EmojiPacks


@dataclass(frozen=True, kw_only=True)
class HitsResult:
    dice: int
    rolls: List[int]
    ones: int
    dice_hits: int
    glitch: Glitch
    limit: int
    gremlins: int
    dice_adjustment: int = 0

    @property
    def original_dice(self):
        return self.dice - self.dice_adjustment

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
        ones = sum(1 for r in rolls if r == 1)
        dice_hits = sum(1 for r in rolls if r in (5, 6))
        glitch = Glitch.NONE
        if ones + gremlins > dice / 2.0:
            glitch = Glitch.CRITICAL if dice_hits == 0 else Glitch.GLITCH
        return HitsResult(dice=dice, rolls=rolls, ones=ones, dice_hits=dice_hits, glitch=glitch, limit=limit, gremlins=gremlins)


    def adjust_dice(self, adjustment: int, rng: random.Random = _default_random):
        new_dice_adjustment: int = self.dice_adjustment + adjustment
        new_dice_to_roll = self.dice + adjustment - len(self.rolls)
        new_rolls = self.rolls + [rng.randint(1, 6) for _ in range(new_dice_to_roll)] if new_dice_to_roll > 0 else self.rolls
        new_dice_count = self.dice + new_dice_adjustment
        counted_dice = new_rolls[0:new_dice_count-1]
        new_dice_hits: int = sum(1 for r in counted_dice if r in (5, 6))
        new_ones = sum(1 for r in counted_dice if r == 1)
        new_glitch: Glitch = Glitch.NONE
        if new_ones * 2 + self.gremlins > new_dice_count:
            new_glitch = Glitch.CRITICAL if new_dice_hits == 0 else Glitch.GLITCH
        return replace(self, rolls=new_rolls, dice=new_dice_count, ones=new_ones, dice_hits=new_dice_hits, glitch=new_glitch, dice_adjustment=new_dice_adjustment)

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
            line = "".join(emojis[x - 1] for x in self.rolls[0:self.dice])
            line += "-~~" + "".join(str(x) for x in self.rolls[self.dice:]) + "~~"
        elif self.dice_adjustment > 0:
            line = "".join(emojis[x - 1] for x in self.rolls[0:self.original_dice])
            line += "+" + "".join(emojis[x - 1] for x in self.rolls[self.original_dice:])
        else:
            line = "".join(emojis[x - 1] for x in self.rolls)
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
