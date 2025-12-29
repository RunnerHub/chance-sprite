# common.py
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from enum import Enum
from typing import List, Optional

import discord
from discord import app_commands
from discord import ui, ButtonStyle

from chance_sprite.emojis.emoji_manager import EmojiPacks

_default_random = random.Random()

class Glitch(Enum):
    NONE = "none"
    GLITCH = "glitch"
    CRITICAL = "critical"

MAX_EMOJI_DICE = 120  # Guard against content limit (~27 characters per emoji, 4096 characters max)
# TODO: per-post limit instead of per-roll

class RollResultView(ui.LayoutView):
    def __init__(self,  roll_result:RollResult, label: str, *, emoji_packs: EmojiPacks | None, roller_id: int | None = None):
        super().__init__(timeout=None)
        self.result = roll_result
        self.roller_id = roller_id
        self.label = label
        self.emoji_packs = emoji_packs
        self._build()

    def _build(self):
        container = self.build_header(self.label, 0x8888FF)
        dice = self.render_roll_with_glitch()
        dice_section = ui.TextDisplay(dice)
        if not self.result.rerolled:
            if self.result.limit <= 0 or self.result.dice_hits < self.result.limit:
                edge_button = ui.Button(style=ButtonStyle.primary, emoji=self.emoji_packs.edge[0])
                edge_button.callback = self.on_edge
                dice_section = ui.Section(dice_section, accessory=edge_button)
        container.add_item(dice_section)
        self.add_item(container)

    async def on_edge(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.roller_id:
            return

        self.result = self.result.reroll_failures()
        self.clear_items()
        self._build()

        # Edit the original message that contains this view
        await interaction.response.edit_message(view=self)

    @staticmethod
    def build_header(label, colour):
        container = ui.Container(accent_color=colour)
        header = label.strip() if label else ""
        if header:
            container.add_item(ui.TextDisplay(f"### {header}"))
            container.add_item(ui.Separator())
        return container

    def render_dice(self) -> str:
        emojis = self.emoji_packs.d6_ex if self.result.explode else self.emoji_packs.d6

        shown = self.result.rolls[:MAX_EMOJI_DICE]
        hidden = len(self.result.rolls) - len(shown)

        line = "".join(emojis[x - 1] for x in shown)
        if hidden > 0:
            line += f"\n(+{hidden} more)"
        return line

    def render_rerolls(self) -> str:
        emojis = self.emoji_packs.d6
        line = "".join(emojis[x - 1] for x in self.result.rerolled_dice)
        return line

    def render_glitch(self):
        if self.result.glitch == Glitch.GLITCH:
            return "`!`" + self.emoji_packs.glitch
        if self.result.glitch == Glitch.CRITICAL:
            return "`!`" + self.emoji_packs.critglitch
        return ""

    @staticmethod
    def render_limit(hits, limit):
        if limit > 0:
            if hits > limit:
                return f" ~~{hits} hit{'' if hits == 1 else 's'}~~ limit **{limit}**"
            else:
                return f" **{hits}** hit{'' if hits == 1 else 's'} ~~limit {limit}~~"
        else:
            return f" **{hits}** hit{'' if hits == 1 else 's'}"

    def render_roll(self):
        line = f"`{self.result.dice}d6:`" + self.render_dice()
        line += self.render_glitch()
        line += self.render_limit(self.result.dice_hits, self.result.limit)
        if self.result.rerolled:
            line += f"\n`edge:`" + self.render_rerolls() + self.render_limit(self.result.dice_hits + self.result.rerolled_hits, self.result.limit)
        return line

    def render_roll_with_glitch(self):
        line = self.render_roll()
        return line

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
    rerolled: bool = False
    rerolled_dice: List[int] | None = None
    rerolled_hits: int | None = None

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

    def reroll_failures(self, rng: random.Random = _default_random):
        rerolls = [rng.randint(1, 6) for _ in range(self.dice - self.dice_hits)]
        new_hits = sum(1 for r in rerolls if r in (5, 6))

        return replace(self, rerolled=True, rerolled_dice=rerolls, rerolled_hits=new_hits)



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
        emoji_packs = interaction.client.emoji_packs
        if emoji_packs:
            view = RollResultView(result, label, emoji_packs=emoji_packs, roller_id=interaction.user.id)
            await interaction.response.send_message(view=view)
        else:
            await interaction.response.send_message("Still loading emojis, please wait!")
        # Todo: Add buttons
        _msg = await interaction.original_response()
