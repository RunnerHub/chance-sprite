# summon.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import discord
from discord import ui
from discord import app_commands

from .common import RollResult, Glitch


@dataclass(frozen=True)
class SummonResult:
    # Inputs
    force: int
    drain_adjust: int  # additive override applied to DV after spirit hits

    # Rolls
    summon: RollResult          # limited by limit/force via RollResult.limit
    resist: RollResult          # spirit resistance; dice = force
    drain: RollResult           # drain resistance roll

    @property
    def net_hits(self) -> int:
        return self.summon.hits - self.resist.hits

    @property
    def succeeded(self) -> bool:
        return self.net_hits > 0

    @property
    def drain_value(self) -> int:
        return max(2, 2 * self.resist.hits) + self.drain_adjust

    @property
    def drain_taken(self) -> int:
        return max(0, self.drain_value - self.drain.hits)

    @property
    def result_color(self) -> int:
        # Critical glitch anywhere = red.
        if (
            self.summon.glitch == Glitch.CRITICAL
            or self.resist.glitch == Glitch.CRITICAL
            or self.drain.glitch == Glitch.CRITICAL
        ):
            return 0xFF0000

        # Any glitch: purple-ish if success, red-ish if fail.
        if (
            self.summon.glitch == Glitch.GLITCH
            or self.resist.glitch == Glitch.GLITCH
            or self.drain.glitch == Glitch.GLITCH
        ):
            return 0xCC44CC if self.succeeded else 0xCC4444

        # Otherwise: base on drain outcome, with failure looking warmer.
        if self.drain_taken > 0:
            return 0xFF8888
        return 0x88FF88 if self.succeeded else 0xFFAA66

    @staticmethod
    def roll(
        *,
        force: int,
        summon_dice: int,
        drain_dice: int,
        limit: Optional[int] = None,
        drain_adjust: int = 0,
    ) -> SummonResult:
        lim = limit or force

        summon = RollResult.roll(int(summon_dice), limit=int(lim))
        resist = RollResult.roll(int(force))
        drain = RollResult.roll(int(drain_dice))

        return SummonResult(
            force=int(force),
            drain_adjust=int(drain_adjust),
            summon=summon,
            resist=resist,
            drain=drain,
        )

    def build_view(self, label: str) -> ui.LayoutView:
        container = RollResult.build_header(label + f"\nForce {self.force}", self.result_color)

        summon_line = "**Summoning:**\n" + self.summon.render_roll_with_glitch()
        container.add_item(ui.TextDisplay(summon_line))

        resist_line = f"**Spirit Resistance:**\n" + self.resist.render_roll_with_glitch()
        container.add_item(ui.TextDisplay(resist_line))

        if self.succeeded:
            container.add_item(ui.TextDisplay(f"Summoned! Net hits: **{self.net_hits}**"))
        else:
            container.add_item(ui.TextDisplay(f"Summoning failed. Net hits: **{self.net_hits}**"))
        container.add_item(ui.Separator())

        dv_note = ""
        if self.drain_adjust != 0:
            sign = "+" if self.drain_adjust > 0 else ""
            dv_note = f" (adj {sign}{self.drain_adjust})"

        drain_line = (
            "**Drain Resistance:**\n"
            + self.drain.render_roll()
            + f" vs. DV{self.drain_value}{dv_note}"
            + self.drain.render_glitch()
        )
        container.add_item(ui.TextDisplay(drain_line))

        if self.drain_taken > 0:
            container.add_item(ui.TextDisplay(f"Took **{self.drain_taken}** Drain!"))
        else:
            container.add_item(ui.TextDisplay("Resisted Drain!"))

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view


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
    async def cmd(
        interaction: discord.Interaction,
        label: str,
        force: app_commands.Range[int, 1, 99],
        summon_dice: app_commands.Range[int, 1, 99],
        drain_dice: app_commands.Range[int, 1, 99],
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
        drain_adjust: app_commands.Range[int, -99, 99] = 0,
    ) -> None:
        result = SummonResult.roll(
            force=int(force),
            summon_dice=int(summon_dice),
            drain_dice=int(drain_dice),
            limit=int(limit) or 0,
            drain_adjust=int(drain_adjust),
        )
        await interaction.response.send_message(view=result.build_view(label))
        _msg = await interaction.original_response()
