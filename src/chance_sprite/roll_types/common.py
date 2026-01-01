# common.py
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Callable

from discord import ui

from chance_sprite.emojis.emoji_manager import EmojiPacks

_default_random = random.Random()

@staticmethod
def build_header(label, colour):
    container = ui.Container(accent_color=colour)
    header = label.strip() if label else ""
    if header:
        container.add_item(ui.TextDisplay(f"### {header}"))
        container.add_item(ui.Separator())
    return container

class Glitch(Enum):
    NONE = "none"
    GLITCH = "glitch"
    CRITICAL = "critical"

MAX_EMOJI_DICE = 120  # Guard against content limit (~27 characters per emoji, 4096 characters max)

BuildViewFn = Callable[[EmojiPacks], ui.LayoutView]

@dataclass(frozen=True)
class HitsResult:
    dice: int
    rolls: List[int]
    ones: int
    dice_hits: int
    glitch: Glitch
    limit: int
    gremlins: int
    explode: bool

    @property
    def hits_limited(self):
        if self.limit > 0:
            return min(self.limit, self.dice_hits)
        else:
            return self.dice_hits


    @staticmethod
    def roll(dice: int, *, limit: int = 0, gremlins: int = 0, explode: bool = False, rng: random.Random = _default_random) -> HitsResult:
        rolls = [rng.randint(1, 6) for _ in range(dice)]
        ones = sum(1 for r in rolls if r == 1)
        dice_hits = sum(1 for r in rolls if r in (5, 6))
        glitch = Glitch.NONE
        if ones * 2 + gremlins > dice:
            glitch = Glitch.CRITICAL if dice_hits == 0 else Glitch.GLITCH

        return HitsResult(dice=dice, rolls=rolls, ones=ones, dice_hits=dice_hits, glitch=glitch, limit=limit, gremlins=gremlins, explode=explode)


    def render_dice(self, *, emoji_packs: EmojiPacks) -> str:
        emojis = emoji_packs.d6_ex if self.explode else emoji_packs.d6
        
        shown = self.rolls[:MAX_EMOJI_DICE]
        hidden = len(self.rolls) - len(shown)

        line = "".join(emojis[x - 1] for x in shown)
        if hidden > 0:
            line += f"\n(+{hidden} more)"
        return line

    def render_glitch(self, *, emoji_packs: EmojiPacks):
        if self.glitch == Glitch.GLITCH:
            return "```diff\n-Glitch!```"
        if self.glitch == Glitch.CRITICAL:
            return "```diff\n-Critical Glitch!```"
        return ""

    def render_roll(self, *, emoji_packs: EmojiPacks):
        line = f"`{self.dice}d6`" + self.render_dice(emoji_packs=emoji_packs)
        if self.limit>0:
            if self.dice_hits > self.limit:
                line += f" ~~{self.dice_hits} hit{'' if self.dice_hits == 1 else 's'}~~ limit **{self.limit}**"
            else:
                line += f" **{self.dice_hits}** hit{'' if self.dice_hits == 1 else 's'} ~~limit {self.limit}~~"
        else:
            line += f" **{self.dice_hits}** hit{'' if self.hits_limited == 1 else 's'}"
        return line

    def render_roll_with_glitch(self, *, emoji_packs: EmojiPacks):
        line = self.render_roll(emoji_packs=emoji_packs)
        line += self.render_glitch(emoji_packs=emoji_packs)
        return line

@dataclass(frozen=True)
class AdditiveResult:
    dice: int
    rolls: List[int]
    total_roll: int

    @staticmethod
    def roll(dice: int, *, rng: random.Random = _default_random) -> HitsResult:
        rolls = [rng.randint(1, 6) for _ in range(dice)]
        total_roll = sum(r for r in rolls)
        return AdditiveResult(dice=dice, rolls=rolls, total_roll=total_roll)

    def render_dice(self, *, emoji_packs: EmojiPacks) -> str:
        emojis = emoji_packs.d6

        shown = self.rolls[:MAX_EMOJI_DICE]
        hidden = len(self.rolls) - len(shown)

        line = "".join(emojis[x - 1] for x in shown)
        if hidden > 0:
            line += f"\n(+{hidden} more)"
        return line
