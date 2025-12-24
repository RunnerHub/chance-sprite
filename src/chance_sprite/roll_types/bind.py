# bind.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import discord
from discord import ui
from discord import app_commands

from .common import RollResult, Glitch


@dataclass(frozen=True)
class BindResult:
    # Inputs
    force: int
    services_in: int
    drain_adjust: int

    # Rolls
    bind: RollResult
    resist: RollResult
    drain: RollResult

    @property
    def net_hits(self) -> int:
        return self.bind.hits - self.resist.hits

    @property
    def succeeded(self) -> bool:
        return self.net_hits > 0

    @property
    def services_out(self) -> int:
        # Binding costs 1 service; on success add net hits; never below 0.
        base = max(0, self.services_in - 1)
        return base + (self.net_hits if self.succeeded else 0)

    @property
    def drain_value(self) -> int:
        return max(2, 2 * self.resist.hits) + self.drain_adjust

    @property
    def drain_taken(self) -> int:
        return max(0, self.drain_value - self.drain.hits)

    @property
    def bind_cost(self) -> int:
        return 25 * self.force

    @property
    def result_color(self) -> int:
        if (
            self.bind.glitch == Glitch.CRITICAL
            or self.resist.glitch == Glitch.CRITICAL
            or self.drain.glitch == Glitch.CRITICAL
        ):
            return 0xFF0000

        if (
            self.bind.glitch == Glitch.GLITCH
            or self.resist.glitch == Glitch.GLITCH
            or self.drain.glitch == Glitch.GLITCH
        ):
            return 0xCC44CC if self.succeeded else 0xCC4444

        if self.succeeded:
            return 0x88FF88
        return 0xFF8888 if self.drain_taken > 0 else 0xFFAA66

    @staticmethod
    def roll(
        *,
        force: int,
        bind_dice: int,
        drain_dice: int,
        services_in: int,
        limit: Optional[int] = None,
        drain_adjust: int = 0,
    ) -> BindResult:
        lim = limit or force

        bind = RollResult.roll(bind_dice, limit=int(lim))
        resist = RollResult.roll(force * 2)
        drain = RollResult.roll(drain_dice)

        return BindResult(
            force=int(force),
            services_in=int(services_in),
            drain_adjust=int(drain_adjust),
            bind=bind,
            resist=resist,
            drain=drain,
        )

    def build_view(self, label: str) -> ui.LayoutView:
        container = RollResult.build_header(label + f"\nForce {self.force}", self.result_color)

        # Up-front bookkeeping people always ask for.
        container.add_item(ui.TextDisplay(f"**Binding Cost:** {self.bind_cost} reagents (25 × Force)"))
        container.add_item(ui.Separator())

        bind_line = "**Binding:**\n" + self.bind.render_roll_with_glitch()
        container.add_item(ui.TextDisplay(bind_line))

        resist_line = f"**Spirit Resistance (2×Force = {2*self.force} dice):**\n" + self.resist.render_roll_with_glitch()
        container.add_item(ui.TextDisplay(resist_line))

        if self.succeeded:
            container.add_item(ui.TextDisplay(f"Bound! Net hits: **{self.net_hits}**"))
        else:
            container.add_item(ui.TextDisplay(f"Binding failed. Net hits: **{self.net_hits}**"))

        container.add_item(ui.TextDisplay(f"Services: **{self.services_in} → {self.services_out}** (binding costs 1)"))
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
    @group.command(name="bind", description="Binding test vs spirit resistance (2×Force) + drain (SR5).")
    @app_commands.describe(
        label="A label to describe the roll (spirit type + prep are a good start).",
        force="Spirit Force (also default limit; spirit resistance uses 2×Force dice).",
        services_in="Services currently owed by the spirit before binding (from summoning).",
        bind_dice="Binding dice pool (1-99).",
        drain_dice="Drain resistance dice pool (1-99).",
        limit="Optional limit override (defaults to Force).",
        drain_adjust="Optional adjustment to drain DV (additive; can be negative).",
    )
    async def cmd(
        interaction: discord.Interaction,
        label: str,
        force: app_commands.Range[int, 1, 99],
        services_in: app_commands.Range[int, 0, 99],
        bind_dice: app_commands.Range[int, 1, 99],
        drain_dice: app_commands.Range[int, 1, 99],
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
        drain_adjust: app_commands.Range[int, -99, 99] = 0,
    ) -> None:
        result = BindResult.roll(
            force=int(force),
            services_in=int(services_in),
            bind_dice=int(bind_dice),
            drain_dice=int(drain_dice),
            limit=int(limit) if limit is not None else None,
            drain_adjust=int(drain_adjust),
        )
        await interaction.response.send_message(view=result.build_view(label))
        _msg = await interaction.original_response()
