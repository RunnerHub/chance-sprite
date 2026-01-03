# simple.py
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Optional, Callable

import discord
from discord import ui, app_commands

from chance_sprite.result_types import BreakTheLimitHitsResult
from chance_sprite.result_types import HitsResult
from chance_sprite.ui.generic_edge_menu import GenericEdgeMenu
from ..discord_sprite import SpriteContext
from ..emojis.emoji_manager import EmojiPacks
from ..message_cache.roll_record import MessageRecord, RollRecordBase
from ..ui.commonui import build_header, RollAccessor

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


@dataclass(kw_only=True, frozen=True)
class SimpleRollResult(RollRecordBase):
    result: HitsResult

    @staticmethod
    def roll(dice: int, *, limit: int = 0, gremlins: int = 0, explode: bool) -> SimpleRollResult:
        if explode:
            return SimpleRollResult(
                result=BreakTheLimitHitsResult.roll_exploding(dice=dice, limit=limit, gremlins=gremlins))
        else:
            return SimpleRollResult(result=HitsResult.roll(dice=dice, limit=limit, gremlins=gremlins))

    def build_view(self, label: str) -> Callable[[EmojiPacks], ui.LayoutView]:
        def _build(emoji_packs: EmojiPacks) -> ui.LayoutView:
            return SimpleResultView(self.result, label, emoji_packs=emoji_packs)
        return _build


def register(group: app_commands.Group, context: SpriteContext) -> None:
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
        primary_view = await context.emoji_manager.apply_emojis(interaction, result.build_view(label))
        await interaction.response.send_message(view=primary_view)
        record = await MessageRecord.from_interaction(
            interaction=interaction,
            label=label,
            result=result
        )
        context.message_cache.put(record)

        roll_accessor = RollAccessor[SimpleRollResult](getter=lambda r: r.result,
                                                       setter=lambda r, v: replace(r, result=v))
        await GenericEdgeMenu(f"Edge for {label}:", roll_accessor, record, context).send_as_followup(interaction)
