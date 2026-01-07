# summon.py
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


class SummonRollView(ui.LayoutView):
    def __init__(self, roll_result: SummonRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        container = build_header(EdgeMenuButton(), label + f"\nForce {roll_result.force}",
                                 self.result_color(roll_result))

        summon_line = "**Summoning:**\n" + roll_result.summon.render_roll_with_glitch(context)
        container.add_item(ui.TextDisplay(summon_line))

        resist_line = f"**Spirit Resistance:**\n" + roll_result.resist.render_roll_with_glitch(context)
        container.add_item(ui.TextDisplay(resist_line))

        if roll_result.succeeded:
            container.add_item(ui.TextDisplay(f"Summoned! Services: **{roll_result.net_hits}**"))
        else:
            container.add_item(ui.TextDisplay(f"Summoning failed."))
        container.add_item(ui.Separator())

        dv_note = ""
        if roll_result.drain_adjust != 0:
            sign = "+" if roll_result.drain_adjust > 0 else ""
            dv_note = f" (adj {sign}{roll_result.drain_adjust})"

        drain_line = (
                "**Drain Resistance:**\n"
                + roll_result.drain.render_roll(context)
                + f" vs. DV{roll_result.drain_value}{dv_note}"
                + roll_result.drain.render_glitch(context)
        )
        container.add_item(ui.TextDisplay(drain_line))

        if roll_result.drain_taken > 0:
            container.add_item(ui.TextDisplay(f"Took **{roll_result.drain_taken}** Drain!"))
        else:
            container.add_item(ui.TextDisplay("Resisted Drain!"))

        self.add_item(container)

    @staticmethod
    def result_color(result: SummonRoll) -> int:
        if (
                result.summon.glitch == Glitch.CRITICAL
                or result.resist.glitch == Glitch.CRITICAL
                or result.drain.glitch == Glitch.CRITICAL
        ):
            return 0xFF0000

        if (
                result.summon.glitch == Glitch.GLITCH
                or result.resist.glitch == Glitch.GLITCH
                or result.drain.glitch == Glitch.GLITCH
        ):
            return 0xCC44CC if result.succeeded else 0xCC4444

        if result.succeeded:
            return 0x88FF88
        return 0xFF8888 if result.drain_taken > 0 else 0xFFAA66


@message_codec.alias("SummonResult")
@dataclass(frozen=True)
class SummonRoll(RollRecordBase):
    # Inputs
    force: int
    drain_adjust: int  # additive override applied to DV after spirit hits

    # Rolls
    summon: HitsResult          # limited by limit/force via RollResult.limit
    resist: HitsResult          # spirit resistance; dice = force
    drain: HitsResult           # drain resistance roll

    @property
    def net_hits(self) -> int:
        return self.summon.hits_limited - self.resist.hits_limited

    @property
    def succeeded(self) -> bool:
        return self.net_hits > 0

    @property
    def drain_value(self) -> int:
        return max(0, max(2, 2 * self.resist.hits_limited) + self.drain_adjust)

    @property
    def drain_taken(self) -> int:
        return max(0, self.drain_value - self.drain.hits_limited)

    @staticmethod
    def roll(
        *,
        force: int,
        summon_dice: int,
        drain_dice: int,
        limit: Optional[int] = None,
        drain_adjust: int = 0,
    ) -> SummonRoll:
        lim = limit or force

        summon = roll_hits(int(summon_dice), limit=int(lim))
        resist = roll_hits(int(force))
        drain = roll_hits(int(drain_dice))

        return SummonRoll(
            force=int(force),
            drain_adjust=int(drain_adjust),
            summon=summon,
            resist=resist,
            drain=drain,
        )

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return SummonRollView(self, label, context)

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        summon_accessor = RollAccessor[SummonRoll](getter=lambda r: r.summon,
                                                     setter=lambda r, v: replace(r, summon=v))
        summon_menu = GenericEdgeMenu(f"Edge Summoning for {record.label}?", summon_accessor, record.message_id,
                                      interaction)
        await interaction.send_as_followup(summon_menu)

        drain_accessor = RollAccessor[SummonRoll](getter=lambda r: r.drain, setter=lambda r, v: replace(r, drain=v))
        drain_menu = GenericEdgeMenu(f"Edge Drain for {record.label}?", drain_accessor, record.message_id, interaction)
        await interaction.send_as_followup(drain_menu)


def register(group: app_commands.Group) -> None:
    @group.command(name="summon", description="Summoning test vs spirit resistance + drain (SR5).")
    @app_commands.describe(
        label="A label to describe the roll (spirit type + task are a good start).",
        force="Spirit Force (also default limit; also spirit resistance dice).",
        summon_dice="Summoning dice pool (1-99).",
        drain_dice="Drain resistance dice pool (1-99).",
        limit="Optional limit override (defaults to Force).",
        drain_adjust="Optional adjustment to drain DV (additive; can be negative).",
    )
    async def cmd(interaction: Interaction[ClientContext],
                  label: str,
                  force: app_commands.Range[int, 1, 99],
                  summon_dice: app_commands.Range[int, 1, 99],
                  drain_dice: app_commands.Range[int, 1, 99],
                  limit: Optional[app_commands.Range[int, 1, 99]] = None,
                  drain_adjust: app_commands.Range[int, -99, 99] = 0,
                  ) -> None:
        result = SummonRoll.roll(
            force=int(force),
            summon_dice=int(summon_dice),
            drain_dice=int(drain_dice),
            limit=limit or 0,
            drain_adjust=int(drain_adjust),
        )
        await InteractionContext(interaction).transmit_result(label=label, result=result)
