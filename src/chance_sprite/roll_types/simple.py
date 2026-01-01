from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import discord
from discord import ui, app_commands

from .common import HitsResult, BuildViewFn, build_header
from ..emojis.emoji_manager import EmojiPacks


@dataclass(frozen=True)
class SimpleRollResult:
    result: HitsResult

    @staticmethod
    def roll(dice: int, *, limit: int = 0, gremlins: int = 0, explode: bool = False) -> SimpleRollResult:
        return SimpleRollResult(HitsResult.roll(dice=dice,  limit=limit, gremlins=gremlins, explode=explode))

    def build_view(self, label: str)  -> BuildViewFn:
        def _build(emoji_packs: EmojiPacks) -> ui.LayoutView:
            container = build_header(label, 0x8888FF)
            dice = self.result.render_roll_with_glitch(emoji_packs=emoji_packs)
            container.add_item(ui.TextDisplay(dice))
            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            return view
        return _build

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
        result = SimpleRollResult.roll(dice=int(dice), limit=limit or 0, gremlins=gremlins or 0)
        interaction.client.send_with_emojis(interaction, result.build_view(label))
