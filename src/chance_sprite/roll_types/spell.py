# src/chance_sprite/sr5/roll_types/spellcast.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import discord
from discord import ui
from discord import app_commands

from .common import RollResult, Glitch


@dataclass(frozen=True)
class SpellcastResult:
    # Inputs
    force: int
    limit: int
    drain_value: int

    # Rolls
    cast: RollResult
    drain: RollResult

    @property
    def cast_hits_limited(self) -> int:
        return min(self.cast.hits, max(self.limit, 1))

    @property
    def drain_succeeded(self) -> Optional[bool]:
        # drain value is a threshold; 0 means no test outcome
        if self.drain_value <= 0:
            return None
        return self.drain.hits >= self.drain_value

    @property
    def drain_net_hits(self) -> int:
        if self.drain_value <= 0:
            return 0
        return self.drain.hits - self.drain_value

    @property
    def result_color(self) -> int:
        """
        Accent based on drain outcome (because that's the "did you take drain?" part),
        but still signal critical glitches.
        """
        succ = self.drain_succeeded
        if self.drain_value <= 0:
            color = 0x8888FF
        else:
            color = 0x88FF88 if succ else 0xFF8888

        # If either roll critically glitches, go red.
        if self.cast.glitch == Glitch.CRITICAL or self.drain.glitch == Glitch.CRITICAL:
            return 0xFF0000

        # If any roll glitches, use purple-ish (success) or red-ish (fail)
        if self.cast.glitch == Glitch.GLITCH or self.drain.glitch == Glitch.GLITCH:
            return 0xCC44CC if (succ is True or self.drain_value <= 0) else 0xCC4444

        return color

    @staticmethod
    def roll(
        *,
        force: int,
        cast_dice: int,
        drain_value: int,
        drain_dice: int,
        limit: Optional[int] = None,
    ) -> SpellcastResult:
        if force < 1:
            raise ValueError("force must be >= 1")
        if cast_dice < 1:
            raise ValueError("cast_dice must be >= 1")
        if cast_dice > 99:
            raise ValueError("cast_dice must be <= 99")
        if drain_dice < 1:
            raise ValueError("drain_dice must be >= 1")
        if drain_dice > 99:
            raise ValueError("drain_dice must be <= 99")
        if drain_value < 0:
            raise ValueError("drain_value must be >= 0")

        lim = force if limit is None else limit
        if lim < 1:
            raise ValueError("limit must be >= 1")

        cast = RollResult.roll(cast_dice, limit=limit or 0)
        drain = RollResult.roll(drain_dice)

        return SpellcastResult(
            force=force,
            limit=lim,
            drain_value=drain_value,
            cast=cast,
            drain=drain,
        )

    def build_view(self, label: str) -> ui.LayoutView:
        container = RollResult.build_header(label+f"\nForce {self.force}", self.result_color)

        # Spellcasting line: show raw hits and limited hits
        cast_line = (
            f"**Spellcasting:**\n"
            + self.cast.render_roll_with_glitch()
        )
        container.add_item(ui.TextDisplay(cast_line))
        container.add_item(ui.Separator())

        # Drain line: threshold-style
        drain_line = (
            f"**Drain:** \n"
            + self.drain.render_roll() + f" vs. DV{self.drain_value}"
            + self.drain.render_glitch()
        )
        container.add_item(ui.TextDisplay(drain_line))

        # Outcome text (drain)
        if self.drain_value > 0:
            outcome = "Resisted Drain!" if self.drain_succeeded else f"Took **{-self.drain_net_hits}** Drain!"
            container.add_item(ui.TextDisplay(outcome))

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view


def register(group: app_commands.Group) -> None:
    @group.command(name="spellcast", description="Spellcasting test + drain resistance (SR5).")
    @app_commands.describe(
        label="A label to describe the roll (spell name and target are a good start).",
        force="Spell Force (also default limit).",
        cast_dice="Spellcasting dice pool (1-99).",
        drain_value="Drain value (threshold for drain resistance).",
        drain_dice="Drain resistance dice pool (1-99).",
        limit="Optional limit override (defaults to Force)."
    )
    async def cmd(
        interaction: discord.Interaction,
        label: str,
        force: app_commands.Range[int, 1, 99],
        cast_dice: app_commands.Range[int, 1, 99],
        drain_value: app_commands.Range[int, 0, 99],
        drain_dice: app_commands.Range[int, 1, 99],
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
    ) -> None:
        result = SpellcastResult.roll(
            force=int(force),
            cast_dice=int(cast_dice),
            drain_value=int(drain_value),
            drain_dice=int(drain_dice),
            limit=int(limit) if limit is not None else None,
        )
        await interaction.response.send_message(view=result.build_view(label))
        _msg = await interaction.original_response()