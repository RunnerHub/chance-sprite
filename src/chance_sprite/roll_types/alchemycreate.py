# spell.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from discord import app_commands, Interaction
from discord import ui

from chance_sprite.result_types import Glitch
from chance_sprite.result_types import HitsResult
from chance_sprite.roller import roll_hits
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..rollui.commonui import build_header, RollAccessor
from ..rollui.edge_menu_persist import EdgeMenuButton
from ..rollui.generic_edge_menu import GenericEdgeMenu
from ..sprite_context import ClientContext, InteractionContext


def _decide_color(roll_result: AlchemyCreateRoll) -> int:
    """
    Accent based on drain outcome (because that's the "did you take drain?" part),
    but still signal critical glitches.
    """
    succ = roll_result.potency > 0
    if roll_result.drain_value <= 0:
        color = 0x8888FF
    else:
        color = 0x88FF88 if succ else 0xFF8888

    # If either roll critically glitches, go red.
    if roll_result.cast.glitch == Glitch.CRITICAL or roll_result.drain.glitch == Glitch.CRITICAL:
        return 0xFF0000

    # If any roll glitches, use purple-ish (success) or red-ish (fail)
    if roll_result.cast.glitch == Glitch.GLITCH or roll_result.drain.glitch == Glitch.GLITCH:
        return 0xCC44CC if (succ or roll_result.drain_value <= 0) else 0xCC4444

    return color


class AlchemyCreateRollView(ui.LayoutView):
    def __init__(self, roll_result: AlchemyCreateRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        container = build_header(EdgeMenuButton(), label + f"\nForce {roll_result.force}",
                                 _decide_color(roll_result))

        # Spellcasting line: show raw hits and limited hits
        cast_line = (
                f"**Alchemy:**\n"
                + roll_result.cast.render_roll_with_glitch(context)
                + f"\nvs.\n"
                + roll_result.resist.render_roll_with_glitch(context)
        )
        if roll_result.potency:
            cast_line += f"\nPotency: **{roll_result.potency}**"
        else:
            cast_line += f"\n**Attempt failed!**"

        cast_section = ui.TextDisplay(cast_line)
        container.add_item(cast_section)
        container.add_item(ui.Separator())

        # Drain line: threshold-style
        drain_line = (
                f"**Drain:** \n"
                + roll_result.drain.render_roll(context) + f" vs. DV{roll_result.drain_value}"
                + roll_result.drain.render_glitch(context)
        )
        container.add_item(ui.TextDisplay(drain_line))

        # Outcome text (drain)
        if roll_result.drain_value > 0:
            outcome = "Resisted Drain!" if roll_result.drain_succeeded else f"Took **{-roll_result.drain_net_hits}** Drain!"
            container.add_item(ui.TextDisplay(outcome))

        self.add_item(container)


@dataclass(frozen=True)
class AlchemyCreateRoll(RollRecordBase):
    # Inputs
    force: int
    limit: int
    drain_value: int

    # Rolls
    cast: HitsResult
    resist: HitsResult
    drain: HitsResult

    @property
    def cast_hits_limited(self) -> int:
        return min(self.cast.hits_limited, max(self.limit, 1))

    @property
    def drain_succeeded(self) -> Optional[bool]:
        # drain value is a threshold; 0 means no test outcome
        if self.drain_value <= 0:
            return None
        return self.drain.hits_limited >= self.drain_value

    @property
    def drain_net_hits(self) -> int:
        if self.drain_value <= 0:
            return 0
        return self.drain.hits_limited - self.drain_value

    @property
    def potency(self):
        return max(self.cast.hits_limited - self.resist.hits_limited, 0)

    @staticmethod
    def roll(
            *,
            force: int,
            cast_dice: int,
            drain_value: int,
            drain_dice: int,
            limit: Optional[int] = None,
    ) -> AlchemyCreateRoll:
        lim = force if limit is None else limit

        cast = roll_hits(cast_dice, limit=limit or 0)

        resist = roll_hits(force)

        drain = roll_hits(drain_dice)

        return AlchemyCreateRoll(
            force=force,
            limit=lim,
            drain_value=drain_value,
            cast=cast,
            resist=resist,
            drain=drain,
        )

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return AlchemyCreateRollView(self, label, context)


    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        cast_accessor = RollAccessor[AlchemyCreateRoll](getter=lambda r: r.cast, setter=lambda r, v: replace(r, cast=v))
        edge_menu1 = GenericEdgeMenu(f"Edge Alchemy for {record.label}?", cast_accessor, record.message_id,
                                     interaction)
        await interaction.send_as_followup(edge_menu1)

        drain_accessor = RollAccessor[AlchemyCreateRoll](getter=lambda r: r.drain,
                                                         setter=lambda r, v: replace(r, drain=v))
        menu2 = GenericEdgeMenu(f"Edge Drain for {record.label}?", drain_accessor, record.message_id, interaction)
        await interaction.send_as_followup(menu2)


def register(group: app_commands.Group) -> None:
    @group.command(name="alchemy_create", description="Alchemy + drain resistance (SR5).")
    @app_commands.describe(
        label="A label to describe the roll (spell name is a good start).",
        force="Force of the preparation (also default limit and opposed test dice pool).",
        cast_dice="Alchemy dice pool (1-99).",
        drain_value="Drain value (threshold for drain resistance).",
        drain_dice="Drain resistance dice pool (1-99).",
        limit="Optional limit override (defaults to Force)."
    )
    async def cmd(
            interaction: Interaction[ClientContext],
            label: str,
            force: app_commands.Range[int, 1, 99],
            cast_dice: app_commands.Range[int, 1, 99],
            drain_value: app_commands.Range[int, 0, 99],
            drain_dice: app_commands.Range[int, 1, 99],
            limit: Optional[app_commands.Range[int, 1, 99]] = None,
    ) -> None:
        result = AlchemyCreateRoll.roll(
            force=int(force),
            cast_dice=int(cast_dice),
            drain_value=int(drain_value),
            drain_dice=int(drain_dice),
            limit=int(limit) if limit is not None else None,
        )
        await InteractionContext(interaction).transmit_result(label=label, result=result)
