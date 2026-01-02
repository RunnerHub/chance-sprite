# startingcash.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import discord
from discord import app_commands
from discord import ui

from chance_sprite.result_types import AdditiveResult
from ..emojis.emoji_manager import EmojiPacks, EmojiManager
from ..ui.commonui import build_header, BuildViewFn


@dataclass(frozen=True, slots=True)
class StartingCashSpec:
    label: str        # display name
    dice: int         # number of d6
    mult: int         # nuyen multiplier
    color: int  # hex

class LifestyleStartingCash(Enum):
    STREET   = StartingCashSpec("Street",   1, 20,  0xFFB3BA)  # pastel red
    SQUATTER = StartingCashSpec("Squatter", 2, 40,  0xFFDFBA)  # pastel orange
    LOW      = StartingCashSpec("Low",      3, 60,  0xFFFFBA)  # pastel yellow
    MIDDLE   = StartingCashSpec("Middle",   4, 100, 0xBAFFC9)  # pastel green
    HIGH     = StartingCashSpec("High",     5, 500, 0xBAE1FF)  # pastel blue
    LUXURY   = StartingCashSpec("Luxury",   6, 1000,0xE0BBE4)  # pastel purple

    @property
    def label(self) -> str:
        return self.value.label

    @property
    def dice(self) -> int:
        return self.value.dice

    @property
    def mult(self) -> int:
        return self.value.mult

    @property
    def color(self) -> int:
        return self.value.color

@dataclass(frozen=True)
class StartingCashResult:
    result: AdditiveResult
    lifestyle: LifestyleStartingCash

    @staticmethod
    def roll(lifestyle: LifestyleStartingCash) -> StartingCashResult:
        return StartingCashResult(result=AdditiveResult.roll(lifestyle.dice), lifestyle=lifestyle)

    def build_view(self, label: str) -> BuildViewFn:
        def _build(emoji_packs: EmojiPacks) -> ui.LayoutView:
            container = build_header(f"{self.lifestyle.label} lifestyle starting cash\n{label}", self.lifestyle.color)

            dice = self.result.render_dice(emoji_packs=emoji_packs)
            total = self.result.total_roll
            nuyen = self.result.total_roll * self.lifestyle.mult
            dice_line = f"`{self.result.dice}d6`{dice} Total: **{total}** × {self.lifestyle.mult}¥"
            outcome = f"# =¥{nuyen}"

            container.add_item(ui.TextDisplay(dice_line))
            container.add_item(ui.TextDisplay(outcome))

            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            return view
        return _build


def register(group: app_commands.Group, emoji_manager: EmojiManager) -> None:
    @group.command(name="startingcash", description="Roll for starting cash.")
    @app_commands.describe(
        label="Who is it for?",
        lifestyle="What is their lifestyle level?"
    )
    @app_commands.choices(lifestyle=[
        app_commands.Choice(
            name=f"{tier.label} ({tier.dice}D6×{tier.mult}¥)",
            value=tier.name
        ) for tier in LifestyleStartingCash
    ])
    async def cmd(
        interaction: discord.Interaction,
        label: str,
        lifestyle: app_commands.Choice[str]
    ) -> None:
        result = StartingCashResult.roll(lifestyle=LifestyleStartingCash[lifestyle.value])
        await emoji_manager.send_with_emojis(interaction, result.build_view(label))
