from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import discord
from discord import ui, app_commands

from chance_sprite.result_types import BreakTheLimitHitsResult
from chance_sprite.result_types import HitsResult
from chance_sprite.ui.menus.generic_edge_menu import GenericEdgeMenu
from ..emojis.emoji_manager import EmojiPacks, EmojiManager
from ..ui.commonui import build_header, BuildViewFn, \
    GenericResultAccessor

log = logging.getLogger(__name__)


class SimpleResultView(ui.LayoutView):
    def __init__(self,  roll_result:HitsResult, label: str, *, emoji_packs: EmojiPacks | None):
        super().__init__(timeout=None)
        self.result = roll_result
        self.label = label
        self.emoji_packs = emoji_packs
        self._build()

    def _build(self):
        container = build_header(self.label, 0x8888FF)
        dice = self.result.render_roll_with_glitch(emoji_packs=self.emoji_packs)
        dice_section = ui.TextDisplay(dice)
        container.add_item(dice_section)
        self.add_item(container)


class SimpleResultAccessor(GenericResultAccessor):
    def __init__(self, view: SimpleResultView, original_message):
        self.view = view
        self.original_message = original_message

    def get(self):
        return self.view.result

    async def update(self, result: HitsResult):
        self.view.result = result
        self.view.clear_items()
        self.view._build()
        # Edit the original message that contains this view
        await self.original_message.edit(view=self.view)


@dataclass(frozen=True)
class SimpleRollResult:
    result: HitsResult

    @staticmethod
    def roll(dice: int, *, limit: int = 0, gremlins: int = 0, explode: bool) -> SimpleRollResult:
        if explode:
            return SimpleRollResult(BreakTheLimitHitsResult.roll_exploding(dice=dice,  limit=limit, gremlins=gremlins))
        else:
            return SimpleRollResult(HitsResult.roll(dice=dice,  limit=limit, gremlins=gremlins))


    def build_view(self, label: str)  -> BuildViewFn:
        def _build(emoji_packs: EmojiPacks) -> ui.LayoutView:
            return SimpleResultView(self.result, label, emoji_packs=emoji_packs)
        return _build


def register(group: app_commands.Group, emoji_manager: EmojiManager) -> None:
    @group.command(name="simple", description="Roll some d6s, Shadowrun-style.")
    @app_commands.describe(
        label="A label to describe the roll.",
        dice="Number of dice (1-99).",
        limit="A limit for the number of hits.",
        gremlins="Reduce the number of 1s required for a glitch.",
        explode="Whether to use exploding dice (Remember to add your edge to the dice, too)."
    )
    async def cmd(
        interaction: discord.Interaction,
        label: str,
        dice: app_commands.Range[int, 1, 99],
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
        gremlins: Optional[app_commands.Range[int, 1, 99]] = None,
        explode: bool = False
    ) -> None:
        result = SimpleRollResult.roll(dice=int(dice), limit=limit or 0, gremlins=gremlins or 0, explode=explode)
        primary_view, original_message = await emoji_manager.send_with_emojis(interaction, result.build_view(label))
        edge_menu = GenericEdgeMenu(f"Edge for {label}:", SimpleResultAccessor(primary_view, original_message), lambda i: i == interaction.user.id)
        followup_message = await interaction.followup.send(view=edge_menu, ephemeral=True)
        edge_menu.followup_message = followup_message