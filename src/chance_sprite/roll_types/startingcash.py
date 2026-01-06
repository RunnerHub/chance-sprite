# startingcash.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from discord import app_commands, Interaction
from discord import ui

from chance_sprite.result_types import AdditiveResult
from ..message_cache import message_codec
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..roller import additive_roll
from ..rollui.commonui import build_header
from ..rollui.edge_menu_persist import EdgeMenuButton
from ..sprite_context import ClientContext, InteractionContext


@dataclass(frozen=True, slots=True)
class StartingCashSpec:
    label: str        # display name
    dice: int         # number of d6
    mult: int         # nuyen multiplier
    color: int  # hex

class LifestyleStartingCash(Enum):
    STREET   = StartingCashSpec("Street",   1, 20,  0xFFB3BA)  # pastel red
    SQUATTER = StartingCashSpec("Squatter", 2, 40,  0xFFDFBA)  # pastel orange
    LOW      = StartingCashSpec("Low",      3, 60,  0xFFFFBA)  # pastel yellow
    MIDDLE   = StartingCashSpec("Middle",   4, 100, 0xBAFFC9)  # pastel green
    HIGH     = StartingCashSpec("High",     5, 500, 0xBAE1FF)  # pastel blue
    LUXURY   = StartingCashSpec("Luxury",   6, 1000,0xE0BBE4)  # pastel purple

    @property
    def label(self) -> str:
        return self.value.label

    @property
    def dice(self) -> int:
        return self.value.dice

    @property
    def mult(self) -> int:
        return self.value.mult

    @property
    def color(self) -> int:
        return self.value.color


@message_codec.alias("StartingCashResult")
@dataclass(frozen=True)
class StartingCashRoll(RollRecordBase):
    result: AdditiveResult
    lifestyle: LifestyleStartingCash

    @staticmethod
    def roll(lifestyle: LifestyleStartingCash) -> StartingCashRoll:
        return StartingCashRoll(result=additive_roll(lifestyle.dice), lifestyle=lifestyle)

    def build_view(self, label: str) -> Callable[[ClientContext], ui.LayoutView]:
        def _build(context: ClientContext) -> ui.LayoutView:
            container = build_header(EdgeMenuButton(),
                                     f"{self.lifestyle.label} lifestyle starting cash\n{label}",
                                     self.lifestyle.color)

            dice = self.result.render_dice(emoji_packs=context.emoji_manager.packs)
            total = self.result.total_roll
            nuyen = self.result.total_roll * self.lifestyle.mult
            dice_line = f"`{self.result.dice}d6`{dice} Total: **{total}** × {self.lifestyle.mult}¥"
            outcome = f"# =¥{nuyen}"

            container.add_item(ui.TextDisplay(dice_line))
            container.add_item(ui.TextDisplay(outcome))

            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            return view
        return _build

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        pass


def register(group: app_commands.Group) -> None:
    @group.command(name="startingcash", description="Roll for starting cash.")
    @app_commands.describe(
        label="Who is it for?",
        lifestyle="What is their lifestyle level?"
    )
    @app_commands.choices(lifestyle=[
        app_commands.Choice(
            name=f"{tier.label} ({tier.dice}D6×{tier.mult}¥)",
            value=tier.name
        ) for tier in LifestyleStartingCash
    ])
    async def cmd(
            interaction: Interaction[ClientContext],
        label: str,
        lifestyle: app_commands.Choice[str]
    ) -> None:
        result = StartingCashRoll.roll(lifestyle=LifestyleStartingCash[lifestyle.value])
        await InteractionContext(interaction).transmit_result(label=label, result=result)
