# other.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from discord import app_commands, ui

from chance_sprite.result_types import AdditiveResult

from ..fungen import Choices, Desc, roll_command
from ..message_cache import message_codec
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..roller import additive_roll
from ..rollui.base_roll_view import BaseRollView
from ..sprite_context import InteractionContext


class StartingCashRollView(BaseRollView):
    def __init__(
        self, roll_result: StartingCashRoll, label: str, context: InteractionContext
    ):
        header_txt = f"{roll_result.lifestyle.label} lifestyle starting cash\n{label}"
        super().__init__(header_txt, roll_result.lifestyle.color, context)

        dice = roll_result.result.render_dice(context)
        total = roll_result.result.total_roll
        nuyen = roll_result.result.total_roll * roll_result.lifestyle.mult
        dice_line = f"`{roll_result.result.dice}d6`{dice} Total: **{total}** × {roll_result.lifestyle.mult}¥"
        outcome = f"# =¥{nuyen}"

        self.add_text(dice_line)
        self.add_text(outcome)


@dataclass(frozen=True, slots=True)
class StartingCashSpec:
    label: str  # display name
    dice: int  # number of d6
    mult: int  # nuyen multiplier
    color: int  # hex


class LifestyleStartingCash(Enum):
    STREET = StartingCashSpec("Street", 1, 20, 0xFFB3BA)  # pastel red
    SQUATTER = StartingCashSpec("Squatter", 2, 40, 0xFFDFBA)  # pastel orange
    LOW = StartingCashSpec("Low", 3, 60, 0xFFFFBA)  # pastel yellow
    MIDDLE = StartingCashSpec("Middle", 4, 100, 0xBAFFC9)  # pastel green
    HIGH = StartingCashSpec("High", 5, 500, 0xBAE1FF)  # pastel blue
    LUXURY = StartingCashSpec("Luxury", 6, 1000, 0xE0BBE4)  # pastel purple

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

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return StartingCashRollView(self, label, context)

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, context: InteractionContext):
        pass


LIFESTYLE_CHOICES = tuple(
    app_commands.Choice(
        name=f"{tier.label} ({tier.dice}D6×{tier.mult}¥)",
        value=tier.name,
    )
    for tier in LifestyleStartingCash
)


@roll_command(desc="Roll for starting cash.")
def roll_startingcash(
    *,
    lifestyle: Annotated[
        str, Desc("What is their lifestyle level?"), Choices(LIFESTYLE_CHOICES)
    ],
) -> StartingCashRoll:
    chosen_lifestyle = LifestyleStartingCash[lifestyle]
    return StartingCashRoll(
        result=additive_roll(chosen_lifestyle.dice), lifestyle=chosen_lifestyle
    )


class InitiativeRollView(BaseRollView):
    def __init__(self, roll: InitiativeRoll, label: str, context: InteractionContext):
        header_txt = label
        super().__init__(header_txt, 0xCC88AA, context)

        dice = roll.result.render_dice(context)
        total = roll.result.total_roll + roll.base
        dice_line = f"`{roll.result.dice}d6`{dice} [**{roll.result.total_roll}**+{roll.base}]\n## Initiative: **{total}**"

        self.add_text(dice_line)


@message_codec.alias("StartingCashResult")
@dataclass(frozen=True)
class InitiativeRoll(RollRecordBase):
    result: AdditiveResult
    base: int

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return InitiativeRollView(self, label, context)

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, context: InteractionContext):
        pass


@roll_command(desc="Roll for starting cash.")
def roll_initiative(
    *,
    base: Annotated[
        app_commands.Range[int, -50, 50],
        Desc(
            "Base initiative value, before dice (usually REA+INT). Can be negative e.g. if you are surprised."
        ),
    ],
    dice: Annotated[
        app_commands.Range[int, 1, 5],
        Desc("Number of initiative dice (1-5)"),
    ],
) -> InitiativeRoll:
    result = additive_roll(dice)
    return InitiativeRoll(result=result, base=base)
