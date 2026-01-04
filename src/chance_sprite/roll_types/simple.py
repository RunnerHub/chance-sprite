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
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..sprite_context import SpriteContext
from ..ui.commonui import build_header, RollAccessor
from ..ui.edge_menu_persist import EdgeMenuButton

log = logging.getLogger(__name__)


class SimpleResultView(ui.LayoutView):
    def __init__(self, roll_result: SimpleRollResult, label: str, *, sprite_context: SpriteContext):
        super().__init__(timeout=None)
        self.roll_result = roll_result
        self.label = label
        self.sprite_context = sprite_context
        self._build()

    def _build(self):
        container = build_header(EdgeMenuButton(self.sprite_context), self.label, 0x8888FF)
        dice = self.roll_result.result.render_roll_with_glitch(emoji_packs=self.sprite_context.emoji_manager.packs)
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

    def build_view(self, label: str) -> Callable[[SpriteContext], ui.LayoutView]:
        def _build(context: SpriteContext) -> ui.LayoutView:
            return SimpleResultView(self, label, sprite_context=context)
        return _build

    @staticmethod
    async def send_edge_menu(record: MessageRecord, context: SpriteContext, interaction: discord.Interaction):
        roll_accessor = RollAccessor[SimpleRollResult](getter=lambda r: r.result,
                                                       setter=lambda r, v: replace(r, result=v))
        await GenericEdgeMenu(f"Edge for {record.label}:", roll_accessor, record.message_id, context).send_as_followup(
            interaction)

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
        log.info(f"Received simple request in Channel {interaction.channel_id}: {interaction.channel}")
        result = SimpleRollResult.roll(dice=int(dice), limit=limit or 0, gremlins=gremlins or 0, explode=explode)
        record = await context.transmit_result(label=label, result=result, interaction=interaction)
