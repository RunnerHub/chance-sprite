# common.py
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Optional

import discord
from discord import ui
from discord import app_commands

_default_random = random.Random()

class Glitch(Enum):
    NONE = "none"
    GLITCH = "glitch"
    CRITICAL = "critical"

D6_EMOJIS = [
    "<:d6r1:1447759071745937438>",
    "<:d6r2:1447759070420537456>",
    "<:d6r3:1447759069124497492>",
    "<:d6r4:1447759074954444812>",
    "<:d6r5:1447759074119778396>",
    "<:d6r6:1447759073096368149>",
]

D6_EX_EMOJIS = [
    "<:d6r1:1447759071745937438>",
    "<:d6r2:1447759070420537456>",
    "<:d6r3:1447759069124497492>",
    "<:d6r4:1447759074954444812>",
    "<:d6r5:1447759074119778396>",
    "<:d6r6ex:1447759092771852288>",
]

MAX_EMOJI_DICE = 120  # Guard against content limit (~27 characters per emoji, 4096 characters max)


@dataclass(frozen=True)
class RollResult:
    dice: int
    rolls: List[int]
    ones: int
    dice_hits: int
    glitch: Glitch
    limit: int
    gremlins: int
    explode: bool

    @property
    def hits(self):
        if self.limit > 0:
            return min(self.limit, self.dice_hits)
        else:
            return self.dice_hits


    @staticmethod
    def roll(dice: int, *, limit: int = 0, gremlins: int = 0, explode: bool = False, rng: random.Random = _default_random) -> RollResult:
        if dice < 1:
            raise ValueError("dice must be >= 1")
        if dice > 99:
            raise ValueError("dice must be <= 99")

        rolls = [rng.randint(1, 6) for _ in range(dice)]
        ones = sum(1 for r in rolls if r == 1)
        dice_hits = sum(1 for r in rolls if r in (5, 6))

        glitch = Glitch.NONE
        if ones * 2 + gremlins > dice:
            glitch = Glitch.CRITICAL if dice_hits == 0 else Glitch.GLITCH

        return RollResult(dice=dice, rolls=rolls, ones=ones, dice_hits=dice_hits, glitch=glitch, limit=limit, gremlins=gremlins, explode=explode)

    @staticmethod
    def build_header(label, colour):
        container = ui.Container(accent_color=colour)
        header = label.strip() if label else ""
        if header:
            container.add_item(ui.TextDisplay(f"### {header}"))
            container.add_item(ui.Separator())
        return container


    def render_dice(self, *, max_dice: int = MAX_EMOJI_DICE) -> str:
        emojis = D6_EX_EMOJIS if self.explode else D6_EMOJIS
        
        shown = self.rolls[:MAX_EMOJI_DICE]
        hidden = len(self.rolls) - len(shown)

        line = "".join(emojis[x - 1] for x in shown)
        if hidden > 0:
            line += f"\n(+{hidden} more)"
        return line

    def render_glitch(self):
        if self.glitch == Glitch.GLITCH:
            return "```diff\n-Glitch!```"
        if self.glitch == Glitch.CRITICAL:
            return "```diff\n-Critical Glitch!```"
        if self.glitch == Glitch.NONE:
            return ""

    def render_roll(self, *, max_dice: int = MAX_EMOJI_DICE):
        line = f"`{self.dice}d6`" + self.render_dice()
        if self.limit>0:
            if self.dice_hits > self.limit:
                line += f" ~~{self.hits} hit{'' if self.dice_hits == 1 else 's'}~~ limit **{self.limit}**"
            else:
                line += f" **{self.hits}** hit{'' if self.dice_hits == 1 else 's'} ~~limit {self.limit}~~"
        else:
            line += f" **{self.hits}** hit{'' if self.hits == 1 else 's'}"
        return line
    def render_roll_with_glitch(self, *, max_dice: int = MAX_EMOJI_DICE):
        line = self.render_roll(max_dice=max_dice)
        line += self.render_glitch()
        return line

    def build_view(self, label: str) -> ui.LayoutView:
        container = self.build_header(label, 0x8888FF)

        dice = self.render_roll_with_glitch()
        container.add_item(ui.TextDisplay(dice))

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view


def register(group: app_commands.Group) -> None:
    @group.command(name="simple", description="Roll some d6s, Shadowrun-style.")
    @app_commands.describe(
        label="A label to describe the roll.",
        dice="Number of dice (1-99).",
        limit="A limit for the number of hits.",
        gremlins="Reduce the number of 1s required for a glitch."
    )
    async def cmd(
        interaction: discord.Interaction,
        label: str,
        dice: app_commands.Range[int, 1, 99],
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
        gremlins: Optional[app_commands.Range[int, 1, 99]] = None
    ) -> None:
        result = RollResult.roll(dice=int(dice), limit=limit or 0, gremlins=gremlins or 0)
        await interaction.response.send_message(view=result.build_view(label))

        # Todo: Add buttons
        _msg = await interaction.original_response()
