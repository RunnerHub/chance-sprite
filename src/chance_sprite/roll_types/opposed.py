from __future__ import annotations

from dataclasses import dataclass

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
    def roll(initiator_dice: int, defender_dice: int) -> OpposedResult:
        initiator = RollResult.roll(initiator_dice)
        defender = RollResult.roll(defender_dice)
        return OpposedResult(initiator=initiator, defender=defender)


    def build_view(self, comment: str) -> ui.LayoutView:
        # Color by outcome
        net = self.net_hits
        if net > 0:
            accent = 0x88FF88
        elif net < 0:
            accent = 0xFF8888
        else:
            accent = 0x8888FF
    
        container = ui.Container(accent_color=accent)
    
        if comment.strip():
            container.add_item(ui.TextDisplay(f"# {comment.strip()}"))
    
        container.add_item(ui.TextDisplay(f"Opposed roll: `[{self.initiator.dice}]` vs. `[{self.defender.dice}]`"))
    
        # Initiator block
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(f"**Initiator:** {self.initiator.render_dice()} [**{self.initiator.hits}** Hits]"))
        if self.initiator.glitch == Glitch.CRITICAL:
            container.add_item(ui.TextDisplay("```diff\n- Critical Glitch!\n```"))
        elif self.initiator.glitch == Glitch.GLITCH:
            container.add_item(ui.TextDisplay("```diff\n- Glitch!\n```"))
    
        # Defender block
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(f"**Defender:** {self.defender.render_dice()} [**{self.defender.hits}** Hits]"))
        if self.defender.glitch == Glitch.CRITICAL:
            container.add_item(ui.TextDisplay("```diff\n- Critical Glitch!\n```"))
        elif self.defender.glitch == Glitch.GLITCH:
            container.add_item(ui.TextDisplay("```diff\n- Glitch!\n```"))
    
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
        initiator_dice="Initiator dice pool (1-99).",
        defender_dice="Defender dice pool (1-99).",
        comment="Optional title/comment.",
    )
    async def cmd(
            interaction: discord.Interaction,
            initiator_dice: app_commands.Range[int, 1, 99],
            defender_dice: app_commands.Range[int, 1, 99],
            comment: str = "",
    ) -> None:
        result = OpposedResult.roll(int(initiator_dice), int(defender_dice))
        await interaction.response.send_message(view=result.build_view(comment))

        # Todo: Add buttons
        _msg = await interaction.original_response()
