# simple.py
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Optional

from discord import ui, app_commands, Interaction

from chance_sprite.result_types import HitsResult
from chance_sprite.roller import roll_hits, roll_exploding
from chance_sprite.rollui.generic_edge_menu import GenericEdgeMenu
from ..message_cache import message_codec
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..rollui.commonui import build_header, RollAccessor
from ..rollui.edge_menu_persist import EdgeMenuButton
from ..sprite_context import ClientContext, InteractionContext

log = logging.getLogger(__name__)


class SimpleResultView(ui.LayoutView):
    def __init__(self, roll_result: SimpleRoll, label: str, *, sprite_context: ClientContext):
        super().__init__(timeout=None)
        self.roll_result = roll_result
        self.label = label
        self.sprite_context = sprite_context
        container = build_header(EdgeMenuButton(), self.label, 0x8888FF)
        dice = self.roll_result.result.render_roll_with_glitch(emoji_packs=self.sprite_context.emoji_manager.packs)
        dice_section = ui.TextDisplay(dice)
        container.add_item(dice_section)
        self.add_item(container)


@message_codec.alias("SimpleRollResult")
@dataclass(kw_only=True, frozen=True)
class SimpleRoll(RollRecordBase):
    result: HitsResult

    @staticmethod
    def roll(dice: int, *, limit: int = 0, gremlins: int = 0, explode: bool) -> SimpleRoll:
        if explode:
            return SimpleRoll(
                result=roll_exploding(dice=dice, limit=limit, gremlins=gremlins))
        else:
            return SimpleRoll(result=roll_hits(dice=dice, limit=limit, gremlins=gremlins))

    def build_view(self, label: str, context: ClientContext) -> ui.LayoutView:
        return SimpleResultView(self, label, sprite_context=context)

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        roll_accessor = RollAccessor[SimpleRoll](getter=lambda r: r.result,
                                                 setter=lambda r, v: replace(r, result=v))
        edge_menu = GenericEdgeMenu(f"Edge for {record.label}:", roll_accessor, record.message_id, interaction)
        await interaction.send_as_followup(edge_menu)


def register(group: app_commands.Group) -> None:
    @group.command(name="simple", description="Roll some d6s, Shadowrun-style.")
    @app_commands.describe(
        label="A label to describe the roll.",
        dice="Number of dice (1-99).",
        limit="A limit for the number of hits.",
        gremlins="Reduce the number of 1s required for a glitch.",
        explode="Whether to use exploding dice (Remember to add your edge to the dice, too)."
    )
    async def cmd(
            interaction: Interaction[ClientContext],
        label: str,
        dice: app_commands.Range[int, 1, 99],
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
        gremlins: Optional[app_commands.Range[int, 1, 99]] = None,
        explode: bool = False
    ) -> None:
        result = SimpleRoll.roll(dice=int(dice), limit=limit or 0, gremlins=gremlins or 0, explode=explode)
        await InteractionContext(interaction).transmit_result(label=label, result=result)
