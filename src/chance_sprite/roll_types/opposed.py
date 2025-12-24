# opposed.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import discord
from discord import ui
from discord import app_commands
from .common import RollResult, Glitch


@dataclass(frozen=True)
class OpposedResult:
    initiator: RollResult
    defender: RollResult

    @property
    def net_hits(self) -> int:
        return self.initiator.hits - self.defender.hits

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
             initiator_gremlins: int, defender_gremlins: int) -> OpposedResult:
        initiator = RollResult.roll(initiator_dice, limit=initiator_limit, gremlins=initiator_gremlins)
        defender = RollResult.roll(defender_dice, limit=defender_limit, gremlins=defender_gremlins)
        return OpposedResult(initiator=initiator, defender=defender)


    def build_view(self, label: str) -> ui.LayoutView:
        # Color by outcome
        net = self.net_hits
        if net > 0:
            accent = 0x88FF88
        elif net < 0:
            accent = 0xFF8888
        else:
            accent = 0x8888FF
    
        container = RollResult.build_header(label, accent)
    
        # Initiator block
        container.add_item(ui.TextDisplay(f"**Initiator:**\n{self.initiator.render_roll_with_glitch()}"))

        container.add_item(ui.Separator())
        # Defender block
        container.add_item(ui.TextDisplay(f"**Defender:**\n{self.defender.render_roll_with_glitch()}"))

        # Outcome
        container.add_item(ui.Separator())
        if net == 0:
            container.add_item(ui.TextDisplay("Tie; Defender wins. (0 net hits)"))
        else:
            container.add_item(ui.TextDisplay(f"{self.outcome} with **{net:+d}** net hits"))
    
        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view


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
        interaction: discord.Interaction,
        label: str,
        initiator_dice: app_commands.Range[int, 1, 99],
        defender_dice: app_commands.Range[int, 1, 99],
        initiator_limit: Optional[app_commands.Range[int, 1, 99]] = None,
        defender_limit: Optional[app_commands.Range[int, 1, 99]] = None,
        initiator_gremlins: Optional[app_commands.Range[int, 1, 99]] = None,
        defender_gremlins: Optional[app_commands.Range[int, 1, 99]] = None
    ) -> None:
        result = OpposedResult.roll(int(initiator_dice), int(defender_dice), initiator_limit=initiator_limit, defender_limit=defender_limit, initiator_gremlins=initiator_gremlins, defender_gremlins=defender_gremlins)
        await interaction.response.send_message(view=result.build_view(label))

        # Todo: Add buttons
        _msg = await interaction.original_response()
