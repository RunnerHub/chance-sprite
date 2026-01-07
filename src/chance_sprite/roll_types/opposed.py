# opposed.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from discord import app_commands, Interaction
from discord import ui

from chance_sprite.result_types import HitsResult
from chance_sprite.roller import roll_hits
from ..message_cache import message_codec
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..rollui.commonui import build_header, RollAccessor
from ..rollui.edge_menu_persist import EdgeMenuButton
from ..rollui.generic_edge_menu import GenericEdgeMenu
from ..sprite_context import ClientContext, InteractionContext


def _decide_color(roll_result: OpposedRoll):
    # Color by outcome
    net = roll_result.net_hits
    if net > 0:
        accent = 0x88FF88
    elif net < 0:
        accent = 0xFF8888
    else:
        accent = 0x8888FF
    return accent


class OpposedRollView(ui.LayoutView):
    def __init__(self, roll_result: OpposedRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)

        menu_button = EdgeMenuButton()
        container = build_header(menu_button, label, _decide_color(roll_result))

        # Initiator block
        container.add_item(ui.TextDisplay(
            f"**Initiator:**\n{roll_result.initiator.render_roll_with_glitch(context)}"))

        container.add_item(ui.Separator())
        # Defender block
        container.add_item(ui.TextDisplay(
            f"**Defender:**\n{roll_result.defender.render_roll_with_glitch(context)}"))

        net = roll_result.net_hits
        # Outcome
        container.add_item(ui.Separator())
        if net == 0:
            container.add_item(ui.TextDisplay("Tie; Defender wins. (0 net hits)"))
        else:
            container.add_item(ui.TextDisplay(f"{roll_result.outcome} with **{net:+d}** net hits"))

        self.add_item(container)

@message_codec.alias("OpposedResult")
@dataclass(frozen=True)
class OpposedRoll(RollRecordBase):
    initiator: HitsResult
    defender: HitsResult

    @property
    def net_hits(self) -> int:
        return self.initiator.hits_limited - self.defender.hits_limited

    @property
    def outcome(self) -> str:
        if self.net_hits > 0:
            return "Initiator wins"
        if self.net_hits < 0:
            return "Defender wins"
        return "Tie (defender wins)"

    @staticmethod
    def roll(initiator_dice: int, defender_dice: int, *,
             initiator_limit: int, defender_limit: int,
             initiator_gremlins: int, defender_gremlins: int) -> OpposedRoll:
        initiator = roll_hits(initiator_dice, limit=initiator_limit, gremlins=initiator_gremlins)
        defender = roll_hits(defender_dice, limit=defender_limit, gremlins=defender_gremlins)
        return OpposedRoll(initiator=initiator, defender=defender)

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return OpposedRollView(self, label, context)

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        result_accessor = RollAccessor[OpposedRoll](getter=lambda r: r.initiator,
                                                    setter=lambda r, v: replace(r, initiator=v))
        menu = GenericEdgeMenu(f"Edge initiator for {record.label}?", result_accessor, record.message_id, interaction)
        await interaction.send_as_followup(menu)


def register(group: app_commands.Group) -> None:
    @group.command(name="opposed", description="Opposed roll: initiator vs defender. Defender wins ties.")
    @app_commands.describe(
        label="A label to describe the roll.",
        initiator_dice="Initiator dice pool (1-99).",
        defender_dice="Defender dice pool (1-99).",
        initiator_limit="Initiator's limit, if applicable.",
        defender_limit="Defender's limit, if applicable.",
        initiator_gremlins="Reduce the number of 1s required for a glitch.",
        defender_gremlins="Reduce the number of 1s required for a glitch."
    )
    async def cmd(
            interaction: Interaction[ClientContext],
        label: str,
        initiator_dice: app_commands.Range[int, 1, 99],
        defender_dice: app_commands.Range[int, 1, 99],
        initiator_limit: Optional[app_commands.Range[int, 1, 99]] = None,
        defender_limit: Optional[app_commands.Range[int, 1, 99]] = None,
        initiator_gremlins: Optional[app_commands.Range[int, 1, 99]] = None,
        defender_gremlins: Optional[app_commands.Range[int, 1, 99]] = None
    ) -> None:
        result = OpposedRoll.roll(
            int(initiator_dice),
            int(defender_dice),
            initiator_limit=initiator_limit or 0,
            defender_limit=defender_limit or 0,
            initiator_gremlins=initiator_gremlins or 0,
            defender_gremlins=defender_gremlins or 0
        )
        await InteractionContext(interaction).transmit_result(label=label, result=result)
