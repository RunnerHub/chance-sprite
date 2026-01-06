# bind.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Callable, Self

from discord import app_commands, Interaction
from discord import ui

from chance_sprite.result_types import Glitch
from chance_sprite.result_types import HitsResult
from chance_sprite.roller import roll_hits
from ..message_cache import message_codec
from ..message_cache.roll_record_base import RollRecordBase
from ..rollui.commonui import build_header, RollAccessor
from ..rollui.edge_menu_persist import EdgeMenuButton
from ..rollui.generic_edge_menu import GenericEdgeMenu
from ..sprite_context import ClientContext, InteractionContext


@message_codec.alias("BindResult")
@dataclass(frozen=True)
class BindingRoll(RollRecordBase):
    # Inputs
    force: int
    services_in: int
    drain_adjust: int

    # Rolls
    bind: HitsResult
    resist: HitsResult
    drain: HitsResult

    @property
    def net_hits(self) -> int:
        return self.bind.hits_limited - self.resist.hits_limited

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
        return max(0, max(2, 2 * self.resist.hits_limited) + self.drain_adjust)

    @property
    def drain_taken(self) -> int:
        return max(0, self.drain_value - self.drain.hits_limited)

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
    ) -> BindingRoll:
        lim = limit or force

        bind = roll_hits(bind_dice, limit=int(lim))
        resist = roll_hits(force * 2)
        drain = roll_hits(drain_dice)

        return BindingRoll(
            force=int(force),
            services_in=int(services_in),
            drain_adjust=int(drain_adjust),
            bind=bind,
            resist=resist,
            drain=drain,
        )

    def build_view(self, label: str) -> Callable[[ClientContext], ui.LayoutView]:
        def _build(context: ClientContext) -> ui.LayoutView:

            menu_button = EdgeMenuButton()
            container = build_header(menu_button,
                                     label + f"\nForce {self.force} | **Binding Cost:** {self.bind_cost} reagents, 1 service",
                                     self.result_color)

            bind_line = "**Binding:**\n" + self.bind.render_roll_with_glitch(emoji_packs=context.emoji_manager.packs)
            container.add_item(ui.TextDisplay(bind_line))

            resist_line = f"**Spirit Resistance:**\n" + self.resist.render_roll_with_glitch(
                emoji_packs=context.emoji_manager.packs)
            container.add_item(ui.TextDisplay(resist_line))

            services_changed = f"Services: **{self.services_in} → {self.services_out}**"
            if self.succeeded:
                container.add_item(ui.TextDisplay(f"Bound! Net hits: **{self.net_hits}**. {services_changed}"))
            else:
                container.add_item(ui.TextDisplay(f"Binding failed. {services_changed}"))
            container.add_item(ui.Separator())

            dv_note = ""
            if self.drain_adjust != 0:
                sign = "+" if self.drain_adjust > 0 else ""
                dv_note = f" (adj {sign}{self.drain_adjust})"

            drain_line = (
                "**Drain Resistance:**\n"
                + self.drain.render_roll(emoji_packs=context.emoji_manager.packs)
                + f" vs. DV{self.drain_value}{dv_note}"
                + self.drain.render_glitch(emoji_packs=context.emoji_manager.packs)
            )
            container.add_item(ui.TextDisplay(drain_line))

            if self.drain_taken > 0:
                container.add_item(ui.TextDisplay(f"Took **{self.drain_taken}** Drain!"))
            else:
                container.add_item(ui.TextDisplay("Resisted Drain!"))

            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            return view
        return _build

    @classmethod
    async def send_edge_menu(cls, record: type[Self], interaction: InteractionContext):
        bind_accessor = RollAccessor[BindingRoll](getter=lambda r: r.bind, setter=lambda r, v: replace(r, bind=v))
        bind_menu = GenericEdgeMenu(f"Edge Binding for {record.label}?", bind_accessor, record.message_id, interaction)
        await interaction.send_as_followup(bind_menu)

        drain_accessor = RollAccessor[BindingRoll](getter=lambda r: r.drain, setter=lambda r, v: replace(r, drain=v))
        drain_menu = GenericEdgeMenu(f"Edge Drain for {record.label}?", drain_accessor, record.message_id, interaction)
        await interaction.send_as_followup(drain_menu)


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
            interaction: Interaction[ClientContext],
        label: str,
        force: app_commands.Range[int, 1, 99],
        services_in: app_commands.Range[int, 0, 99],
        bind_dice: app_commands.Range[int, 1, 99],
        drain_dice: app_commands.Range[int, 1, 99],
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
        drain_adjust: app_commands.Range[int, -99, 99] = 0,
    ) -> None:
        result = BindingRoll.roll(
            force=int(force),
            services_in=int(services_in),
            bind_dice=int(bind_dice),
            drain_dice=int(drain_dice),
            limit=int(limit) if limit is not None else None,
            drain_adjust=int(drain_adjust),
        )
        await InteractionContext(interaction).transmit_result(label=label, result=result)
