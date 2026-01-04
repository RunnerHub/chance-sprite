# threshold.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Callable

import discord
from discord import app_commands
from discord import ui

from chance_sprite.result_types import Glitch
from chance_sprite.result_types import HitsResult
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..sprite_context import SpriteContext
from ..ui.commonui import build_header, RollAccessor
from ..ui.edge_menu_persist import EdgeMenuButton
from ..ui.generic_edge_menu import GenericEdgeMenu


@dataclass(frozen=True)
class ThresholdResult(RollRecordBase):
    result: HitsResult
    threshold: int

    @property
    def succeeded(self) -> Optional[bool]:
        if self.threshold <= 0:
            return None
        return self.result.hits_limited >= self.threshold

    @property
    def net_hits(self) -> int:
        if self.threshold <= 0:
            return 0
        return self.result.hits_limited - self.threshold

    @staticmethod
    def roll(dice: int, threshold: int, *, limit: int = 0, gremlins: int = 0) -> ThresholdResult:
        if threshold < 0:
            raise ValueError("threshold must be >= 0")
        return ThresholdResult(result=HitsResult.roll(dice, limit=limit, gremlins=gremlins), threshold=threshold)

    @property
    def result_color(self) -> int:
        succ = self.succeeded
        if self.threshold <= 0:
            color = 0x8888FF
        else:
            color = 0x88FF88 if succ else 0xFF8888

        if self.result.glitch == Glitch.CRITICAL:
            color = 0xFF0000
        if self.result.glitch == Glitch.GLITCH:
            color = 0xCC44CC if succ else 0xCC4444
        return color

    def build_view(self, label: str) -> Callable[[SpriteContext], ui.LayoutView]:
        def _build(context: SpriteContext) -> ui.LayoutView:
            container = build_header(EdgeMenuButton(context), label, self.result_color)

            dice = self.result.render_roll(emoji_packs=context.emoji_manager.packs)
            if self.threshold:
                dice += f" vs ({self.threshold})"
            glitch = self.result.render_glitch(emoji_packs=context.emoji_manager.packs)
            if glitch:
                dice += "\n" + glitch
            container.add_item(ui.TextDisplay(dice))

            if self.threshold > 0:
                outcome = "Succeeded!" if self.succeeded else "Failed!"
                container.add_item(ui.TextDisplay(f"**{outcome}** ({self.net_hits:+d} net)"))

            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            return view
        return _build

    @staticmethod
    async def send_edge_menu(record: MessageRecord, context: SpriteContext, interaction: discord.Interaction):
        result_accessor = RollAccessor[ThresholdResult](getter=lambda r: r.result,
                                                        setter=lambda r, v: replace(r, result=v))
        await GenericEdgeMenu(f"Edge for {record.label}:", result_accessor, record.message_id,
                              context).send_as_followup(interaction)



def register(group: app_commands.Group, context: SpriteContext) -> None:
    @group.command(name="threshold", description="Roll some d6s, Shadowrun-style.")
    @app_commands.describe(
        label="A label to describe the roll.",
        dice="Number of dice (1-99).",
        threshold="Threshold to reach (optional).",
        limit="A limit for the number of hits.",
        gremlins="Reduce the number of 1s required for a glitch."
    )
    async def cmd(
        interaction: discord.Interaction,
        label: str,
        dice: app_commands.Range[int, 1, 99],
        threshold: app_commands.Range[int, 0, 99] = 0,
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
        gremlins: Optional[app_commands.Range[int, 1, 99]] = None
    ) -> None:
        result = ThresholdResult.roll(dice=int(dice), threshold=threshold or 0, limit=limit or 0, gremlins=gremlins or 0)
        await context.transmit_result(label=label, result=result, interaction=interaction)
