from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List

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
    hits: int
    glitch: Glitch
    limit: int
    gremlins: int
    explode: bool

    @staticmethod
    def roll(dice: int, *, limit: int = 0, gremlins: int = 0, explode: bool = False, rng: random.Random = _default_random) -> RollResult:
        if dice < 1:
            raise ValueError("dice must be >= 1")
        if dice > 99:
            raise ValueError("dice must be <= 99")

        rolls = [rng.randint(1, 6) for _ in range(dice)]
        ones = sum(1 for r in rolls if r == 1)
        hits = sum(1 for r in rolls if r in (5, 6))

        glitch = Glitch.NONE
        if ones * 2 + gremlins > dice:
            glitch = Glitch.CRITICAL if hits == 0 else Glitch.GLITCH

        return RollResult(dice=dice, rolls=rolls, ones=ones, hits=hits, glitch=glitch, limit=limit, gremlins=gremlins, explode=explode)

    @staticmethod
    def build_header(comment, colour):
        container = ui.Container(accent_color=colour)
        header = comment.strip() if comment else ""
        if header:
            container.add_item(ui.TextDisplay(f"## {header}"))
            container.add_item(ui.Separator())


    def render_dice(self, *, max_dice: int = MAX_EMOJI_DICE) -> str:
        emojis = D6_EX_EMOJIS if self.explode else D6_EMOJIS
        
        shown = self.rolls[:MAX_EMOJI_DICE]
        hidden = len(self.rolls) - len(shown)

        line = "".join(emojis[x - 1] for x in shown)
        if hidden > 0:
            line += f"\n(+{hidden} more)"
        return line

    def render_roll(self, *, max_dice: int = MAX_EMOJI_DICE):
        line = f"`[{self.dice}]`" + self.render_dice()
        if limit>0:
            if self.hits > self.limit:
                line += f" {self.hits} hit{'' if self.hits == 1 else 's'}, limited to **{self.limit}**"
            else:
                line += f" **{self.hits}** hit{'' if self.hits == 1 else 's'} (limit {self.limit})"
        else:
            line += f" **{self.hits}** hit{'' if self.hits == 1 else 's'}"
        return line

    def render_glitch(self):
        if self.glitch == Glitch.GLITCH:
            return "```diff\n-Glitch!```"
        if self.glitch == Glitch.CRITICAL:
            return "```diff\n-Critical Glitch!```"

    def build_view(self, comment: str) -> ui.LayoutView:
        container = self.build_header(comment, 0x8888FF)

        dice = render_roll()

        container.add_item(ui.TextDisplay(dice))

        if self.glitch == Glitch.CRITICAL:
            container.add_item(ui.TextDisplay("### **Critical Glitch!**"))
        elif self.glitch == Glitch.GLITCH:
            container.add_item(ui.TextDisplay("### Glitch!"))

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view


def register(group: app_commands.Group) -> None:
    @group.command(name="simple", description="Roll some d6s, Shadowrun-style.")
    @app_commands.describe(
        dice="Number of dice (1-99).",
        comment="A comment to describe the roll.",
    )
    async def cmd(
        interaction: discord.Interaction,
        dice: app_commands.Range[int, 1, 99],
        comment: str = "",
    ) -> None:
        result = RollResult.roll(dice=int(dice))
        await interaction.response.send_message(view=result.build_view(comment))

        # Todo: Add buttons
        _msg = await interaction.original_response()
