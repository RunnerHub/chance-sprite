# spell.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Callable

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


@message_codec.alias("SpellcastResult")
@dataclass(frozen=True)
class SpellRoll(RollRecordBase):
    # Inputs
    force: int
    limit: int
    drain_value: int

    # Rolls
    cast: HitsResult
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
    ) -> SpellRoll:
        lim = force if limit is None else limit

        cast = roll_hits(cast_dice, limit=limit or 0)

        drain = roll_hits(drain_dice)

        return SpellRoll(
            force=force,
            limit=lim,
            drain_value=drain_value,
            cast=cast,
            drain=drain,
        )

    def build_view(self, label: str) -> Callable[[ClientContext], ui.LayoutView]:
        def _build(context: ClientContext) -> ui.LayoutView:
            container = build_header(EdgeMenuButton(), label + f"\nForce {self.force}", self.result_color)

            # Spellcasting line: show raw hits and limited hits
            cast_line = (
                f"**Spellcasting:**\n"
                + self.cast.render_roll_with_glitch(emoji_packs=context.emoji_manager.packs)
            )
            container.add_item(ui.TextDisplay(cast_line))
            container.add_item(ui.Separator())

            # Drain line: threshold-style
            drain_line = (
                f"**Drain:** \n"
                + self.drain.render_roll(emoji_packs=context.emoji_manager.packs) + f" vs. DV{self.drain_value}"
                + self.drain.render_glitch(emoji_packs=context.emoji_manager.packs)
            )
            container.add_item(ui.TextDisplay(drain_line))

            # Outcome text (drain)
            if self.drain_value > 0:
                outcome = "Resisted Drain!" if self.drain_succeeded else f"Took **{-self.drain_net_hits}** Drain!"
                container.add_item(ui.TextDisplay(outcome))

            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            return view
        return _build

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        cast_accessor = RollAccessor[SpellRoll](getter=lambda r: r.cast, setter=lambda r, v: replace(r, cast=v))
        edge_menu1 = GenericEdgeMenu(f"Edge Spellcasting for {record.label}?", cast_accessor, record.message_id,
                                     interaction)
        await interaction.send_as_followup(edge_menu1)

        drain_accessor = RollAccessor[SpellRoll](getter=lambda r: r.drain,
                                                       setter=lambda r, v: replace(r, drain=v))
        menu2 = GenericEdgeMenu(f"Edge Drain for {record.label}?", drain_accessor, record.message_id, interaction)
        await interaction.send_as_followup(menu2)


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
            interaction: Interaction[ClientContext],
        label: str,
        force: app_commands.Range[int, 1, 99],
        cast_dice: app_commands.Range[int, 1, 99],
        drain_value: app_commands.Range[int, 0, 99],
        drain_dice: app_commands.Range[int, 1, 99],
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
    ) -> None:
        result = SpellRoll.roll(
            force=int(force),
            cast_dice=int(cast_dice),
            drain_value=int(drain_value),
            drain_dice=int(drain_dice),
            limit=int(limit) if limit is not None else None,
        )
        await (InteractionContext(interaction).transmit_result(label=label, result=result))
