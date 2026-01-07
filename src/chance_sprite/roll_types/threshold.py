# threshold.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from discord import app_commands, Interaction
from discord import ui

from chance_sprite.result_types import Glitch
from chance_sprite.result_types import HitsResult
from chance_sprite.roller import roll_hits
from ..message_cache import message_codec
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..rollui.commonui import build_header, RollAccessor
from ..rollui.edge_menu_persist import EdgeMenuButton
from ..rollui.generic_edge_menu import GenericEdgeMenu
from ..sprite_context import ClientContext, InteractionContext


class ThresholdView(ui.LayoutView):
    def __init__(self, roll_result: ThresholdRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        container = build_header(EdgeMenuButton(), label, roll_result.result_color)

        dice = roll_result.result.render_roll(context)
        if roll_result.threshold:
            dice += f" vs ({roll_result.threshold})"
        glitch = roll_result.result.render_glitch(context)
        if glitch:
            dice += "\n" + glitch
        container.add_item(ui.TextDisplay(dice))

        if roll_result.threshold > 0:
            outcome = "Succeeded!" if roll_result.succeeded else "Failed!"
            container.add_item(ui.TextDisplay(f"**{outcome}** ({roll_result.net_hits:+d} net)"))

        self.add_item(container)


@message_codec.alias("ThresholdResult")
@dataclass(frozen=True)
class ThresholdRoll(RollRecordBase):
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
    def roll(dice: int, threshold: int, *, limit: int = 0, gremlins: int = 0):
        if threshold < 0:
            raise ValueError("threshold must be >= 0")
        return ThresholdRoll(result=roll_hits(dice, limit=limit, gremlins=gremlins), threshold=threshold)

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

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return ThresholdView(self, label, context)

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        result_accessor = RollAccessor[ThresholdRoll](getter=lambda r: r.result,
                                                        setter=lambda r, v: replace(r, result=v))
        menu = GenericEdgeMenu(f"Edge for {record.label}:", result_accessor, record.message_id, interaction)
        await interaction.send_as_followup(menu)


def register(group: app_commands.Group) -> None:
    @group.command(name="threshold", description="Roll some d6s, Shadowrun-style.")
    @app_commands.describe(
        label="A label to describe the roll.",
        dice="Number of dice (1-99).",
        threshold="Threshold to reach (optional).",
        limit="A limit for the number of hits.",
        gremlins="Reduce the number of 1s required for a glitch."
    )
    async def cmd(interaction: Interaction[ClientContext],
                  label: str,
                  dice: app_commands.Range[int, 1, 99],
                  threshold: app_commands.Range[int, 0, 99] = 0,
                  limit: Optional[app_commands.Range[int, 1, 99]] = None,
                  gremlins: Optional[app_commands.Range[int, 1, 99]] = None
                  ) -> None:
        result = ThresholdRoll.roll(dice=int(dice), threshold=threshold or 0, limit=limit or 0, gremlins=gremlins or 0)
        await InteractionContext(interaction).transmit_result(label=label, result=result)
