# opposed.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import discord
from discord import app_commands
from discord import ui

from .common import HitsResult, BuildViewFn, build_header
from ..emojis.emoji_manager import EmojiPacks


@dataclass(frozen=True)
class OpposedResult:
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
             initiator_gremlins: int, defender_gremlins: int) -> OpposedResult:
        initiator = HitsResult.roll(initiator_dice, limit=initiator_limit, gremlins=initiator_gremlins)
        defender = HitsResult.roll(defender_dice, limit=defender_limit, gremlins=defender_gremlins)
        return OpposedResult(initiator=initiator, defender=defender)


    def build_view(self, label: str) -> BuildViewFn:
        def _build(emoji_packs: EmojiPacks) -> ui.LayoutView:
            # Color by outcome
            net = self.net_hits
            if net > 0:
                accent = 0x88FF88
            elif net < 0:
                accent = 0xFF8888
            else:
                accent = 0x8888FF

            container = build_header(label, accent)

            # Initiator block
            container.add_item(ui.TextDisplay(f"**Initiator:**\n{self.initiator.render_roll_with_glitch(emoji_packs=emoji_packs)}"))

            container.add_item(ui.Separator())
            # Defender block
            container.add_item(ui.TextDisplay(f"**Defender:**\n{self.defender.render_roll_with_glitch(emoji_packs=emoji_packs)}"))

            # Outcome
            container.add_item(ui.Separator())
            if net == 0:
                container.add_item(ui.TextDisplay("Tie; Defender wins. (0 net hits)"))
            else:
                container.add_item(ui.TextDisplay(f"{self.outcome} with **{net:+d}** net hits"))

            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            return view
        return _build


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
        result = OpposedResult.roll(
            int(initiator_dice),
            int(defender_dice),
            initiator_limit=initiator_limit or 0,
            defender_limit=defender_limit or 0,
            initiator_gremlins=initiator_gremlins or 0,
            defender_gremlins=defender_gremlins or 0
        )
        interaction.client.send_with_emojis(interaction, result.build_view(label))