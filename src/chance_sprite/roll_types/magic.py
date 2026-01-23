# magic.py
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Annotated, Optional

from discord import ui
from discord.app_commands import Range

from chance_sprite.fungen import Desc, roll_command
from chance_sprite.message_cache import message_codec
from chance_sprite.message_cache.message_record import MessageRecord
from chance_sprite.message_cache.roll_record_base import ResistableRoll, RollRecordBase
from chance_sprite.result_types import HitsResult
from chance_sprite.roller import roll_exploding, roll_hits
from chance_sprite.rollui.base_menu_view import BaseMenuView
from chance_sprite.rollui.base_roll_view import BaseRollView
from chance_sprite.rollui.modal_inputs import LabeledNumberField
from chance_sprite.rollui.roll_accessor import RollAccessor
from chance_sprite.rollui.roll_view_persist import EdgeMenuButton, ResistButton
from chance_sprite.sprite_context import InteractionContext
from chance_sprite.sprite_utils import Glitch, sign_int

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlchemyCreateRoll(RollRecordBase):
    # Inputs
    force: int
    drain_value: int

    # Rolls
    cast: HitsResult
    resist: HitsResult
    drain: HitsResult

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
    def potency(self):
        return max(self.cast.hits_limited - self.resist.hits_limited, 0)

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return AlchemyCreateRollView(self, label, context)

    @classmethod
    async def send_menu(cls, record: MessageRecord, context: InteractionContext):
        cast_accessor = RollAccessor[AlchemyCreateRoll](
            getter=lambda r: r.cast, setter=lambda r, v: replace(r, cast=v)
        )
        drain_accessor = RollAccessor[AlchemyCreateRoll](
            getter=lambda r: r.drain, setter=lambda r, v: replace(r, drain=v)
        )
        menu = BaseMenuView(record_id=record.message_id)
        menu.add_text(f"Alchemy roll for {record.label}")
        menu.add_standard_buttons(record.roll_result, cast_accessor)

        @menu.modal_button(
            "±F",
            title="Adjust Force",
            body="Positive numbers increase the Force, negative numbers decrease it.",
            fields=[LabeledNumberField("Force", -50, 50)],
        )
        def adjust_force_button(
            roll: AlchemyCreateRoll, context: InteractionContext, force_mod: int
        ) -> AlchemyCreateRoll:
            new_limit = (
                roll.force + force_mod
                if roll.cast.limit == roll.force
                else roll.cast.limit
            )
            return replace(
                roll,
                force=roll.force + force_mod,
                cast=roll.cast.adjust_limit(new_limit),
                drain_value=roll.drain_value + force_mod,
                resist=roll.resist.adjust_dice(force_mod),
            )

        @menu.modal_button(
            "±DV",
            title="Adjust Drain Value Modifier",
            body="Enter the new drain code, relative to Force.",
            fields=[LabeledNumberField("DV", -50, 50, placeholder="e.g. -3")],
        )
        def adjust_dv_button(roll: AlchemyCreateRoll, context: InteractionContext, dv_mod: int) -> AlchemyCreateRoll:
            return replace(roll, drain_value=roll.force + dv_mod)

        menu.add_text(f"Drain roll for {record.label}")
        menu.add_edge_buttons(record.roll_result, drain_accessor)
        menu.add_adjust_dice_button(record.roll_result, drain_accessor)

        await context.send_as_followup(menu)


@roll_command(desc="Roll to create an alchemical preparation.")
def roll_alchemy_create(
    *,
    force: Annotated[
        Range[int, 1, 50],
        Desc("Force of the alchemical preparation attempt."),
    ],
    alchemy_dice: Annotated[Range[int, 1, 99], Desc("Dice pool for alchemy.")],
    drain_code: Annotated[
        Range[int, -50, 50],
        Desc("Drain value modifier, relative to Force. e.g. `-3`"),
    ],
    drain_dice: Annotated[Range[int, 1, 99], Desc("Dice pool for resisting drain.")],
    limit_override: Annotated[
        Optional[Range[int, 0, 50]],
        Desc("Optional limit override (defaults to Force)."),
    ] = None,
    pre_edge: Annotated[
        bool, Desc("Pre-edge the test to create a preparation.")
    ] = False,
) -> AlchemyCreateRoll:
    if pre_edge:
        cast = roll_exploding(alchemy_dice)
    else:
        cast = roll_hits(alchemy_dice, limit=limit_override or force)
    resist = roll_hits(force)
    drain = roll_hits(drain_dice)

    return AlchemyCreateRoll(
        force=force,
        drain_value=force + drain_code,
        cast=cast,
        resist=resist,
        drain=drain,
    )


@message_codec.alias("ResistedAlchemyRoll")
@dataclass(frozen=True)
class AlchemyActivateRoll(ResistableRoll):
    # Inputs
    force: int
    potency: int
    practiced: int
    # Rolls
    cast: HitsResult
    resistance_rolls: dict[int, HitsResult] = field(default_factory=dict)

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return AlchemyActivateRollView(self, label, context)

    @classmethod
    async def send_menu(cls, record: MessageRecord, context: InteractionContext):
        user_id = context.interaction.user.id
        if user_id in record.roll_result.resistance_rolls.keys():
            menu = BaseMenuView(record_id=record.message_id)
            resist_accessor = RollAccessor[AlchemyActivateRoll](
                getter=lambda r: r.resistance_rolls[user_id],
                setter=lambda r, v: replace(
                    r, resistance_rolls={**r.resistance_rolls, user_id: v}
                ),
            )
            menu.add_text(f"Resistance roll for {record.label}")
            menu.add_edge_buttons(record.roll_result, resist_accessor)
            menu.add_adjust_dice_button(record.roll_result, resist_accessor)

            await context.send_as_followup(menu)

    def current_owners(self, record: MessageRecord, context: InteractionContext):
        return [record.owner_id, *self.resistance_rolls.keys()]

    def resistance_target(self) -> int:
        return self.cast.hits_limited

    def already_resisted(self) -> list[int]:
        return [*self.resistance_rolls.keys()]

    def resist(
        self, context: InteractionContext, dice: int, limit: int, pre_edge: bool
    ) -> ResistableRoll:
        if pre_edge:
            resist_roll = roll_exploding(dice, limit=limit, gremlins=0)
        else:
            resist_roll = roll_hits(dice, limit=limit, gremlins=0)
        user_id = context.interaction.user.id
        return replace(
            self, resistance_rolls={**self.resistance_rolls, user_id: resist_roll}
        )

@roll_command(desc="Roll to activate an existing alchemical preparation.")
def roll_alchemy_activate(
    *,
    force: Annotated[Range[int, 1, 50], Desc("Force of the alchemical preparation.")],
    potency: Annotated[
        Range[int, 1, 99], Desc("Potency of the alchemical preparation.")
    ],
    practiced: Annotated[
        Range[int, -50, 50],
        Desc("Any dice bonus from Practiced Alchemist"),
    ] = 0,
    resistable: Annotated[
        bool, Desc("Whether others may roll to resist this spell.")
    ] = True,
) -> AlchemyActivateRoll:
    dice = force + potency + practiced
    limit = force
    cast = roll_hits(dice, limit=limit)

    return AlchemyActivateRoll(
        force=force,
        potency=potency,
        practiced=practiced,
        cast=cast,
        resistable=resistable,
    )


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

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return BindingRollView(self, label, context)

    @classmethod
    async def send_menu(cls, record: MessageRecord, context: InteractionContext):
        menu = BaseMenuView(record_id=record.message_id)
        bind_accessor = RollAccessor[BindingRoll](
            getter=lambda r: r.bind, setter=lambda r, v: replace(r, bind=v)
        )
        menu.add_text(f"Binding roll for {record.label}")
        menu.add_standard_buttons(record.roll_result, bind_accessor)

        @menu.modal_button(
            "±F",
            title="Adjust Force",
            body="Positive numbers increase the Force, negative numbers decrease it.",
            fields=[LabeledNumberField("Force", -50, 50)],
        )
        def adjust_force_button(roll: BindingRoll, context: InteractionContext, force_mod: int) -> BindingRoll:
            new_limit = (
                roll.force + force_mod
                if roll.bind.limit == roll.force
                else roll.bind.limit
            )
            return replace(
                roll,
                force=roll.force + force_mod,
                bind=roll.bind.adjust_limit(new_limit),
                resist=roll.resist.adjust_dice(force_mod * 2),
            )

        @menu.modal_button(
            "±DV",
            title="Adjust Drain Value Modifier",
            body="Positive numbers increase the DV, negative numbers decrease it.",
            fields=[LabeledNumberField("DV", -50, 50)],
        )
        def adjust_dv_button(roll: BindingRoll, context: InteractionContext, dv_mod: int) -> BindingRoll:
            return replace(roll, drain_adjust=dv_mod)

        drain_accessor = RollAccessor[BindingRoll](
            getter=lambda r: r.drain, setter=lambda r, v: replace(r, drain=v)
        )
        menu.add_text(f"Drain roll for {record.label}")
        menu.add_edge_buttons(record.roll_result, drain_accessor)
        menu.add_adjust_dice_button(record.roll_result, drain_accessor)
        await context.send_as_followup(menu)


@roll_command(desc="Roll to bind a summoned spirit. Costs a task, and reagents.")
def roll_binding(
    *,
    force: Annotated[Range[int, 1, 50], Desc("Force of the spirit.")],
    bind_dice: Annotated[Range[int, 1, 99], Desc("Dice pool for binding.")],
    drain_dice: Annotated[Range[int, 1, 99], Desc("Dice pool for resisting drain.")],
    services_in: Annotated[
        Range[int, 1, 50], Desc("Services before the binding attempt.")
    ],
    limit: Annotated[
        Optional[Range[int, 0, 50]],
        Desc("Optional limit (defaults to Force)."),
    ] = None,
    drain_adjust: Annotated[
        Range[int, -50, 50], Desc("Modifier applied to drain.")
    ] = 0,
    pre_edge: Annotated[bool, Desc("Pre-edge the binding roll.")] = False,
) -> BindingRoll:
    if pre_edge:
        bind = roll_exploding(bind_dice)
    else:
        bind = roll_hits(bind_dice, limit=limit or force)
    resist = roll_hits(force * 2)
    drain = roll_hits(drain_dice)

    return BindingRoll(
        force=force,
        services_in=services_in,
        drain_adjust=drain_adjust,
        bind=bind,
        resist=resist,
        drain=drain,
    )


@message_codec.alias("ResistedSpellRoll")
@message_codec.alias("SpellcastResult")
@dataclass(frozen=True)
class SpellRoll(ResistableRoll):
    # Inputs
    force: int
    drain_value: int

    # Rolls
    cast: HitsResult
    drain: HitsResult
    opposition: HitsResult | None = None
    resistance_rolls: dict[int, HitsResult] = field(default_factory=dict)

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

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return SpellRollView(self, label, context)

    @classmethod
    async def send_menu(cls, record: MessageRecord, context: InteractionContext):
        user_id = context.interaction.user.id
        menu = BaseMenuView(record_id=record.message_id)
        if user_id == record.owner_id:
            cast_accessor = RollAccessor[SpellRoll](
                getter=lambda r: r.cast, setter=lambda r, v: replace(r, cast=v)
            )
            drain_accessor = RollAccessor[SpellRoll](
                getter=lambda r: r.drain, setter=lambda r, v: replace(r, drain=v)
            )

            menu.add_text(f"Spellcasting roll for {record.label}")
            menu.add_standard_buttons(record.roll_result, cast_accessor)

            @menu.modal_button(
                "±F",
                title="Adjust Force",
                body="Positive numbers increase the Force, negative numbers decrease it.",
                fields=[LabeledNumberField("Force", -50, 50)],
            )
            def adjust_force_button(roll: SpellRoll, context: InteractionContext, force_mod: int) -> SpellRoll:
                new_limit = (
                    roll.force + force_mod
                    if roll.cast.limit == roll.force
                    else roll.cast.limit
                )
                return replace(
                    roll,
                    force=roll.force + force_mod,
                    cast=roll.cast.adjust_limit(new_limit),
                    drain_value=roll.drain_value + force_mod,
                )

            @menu.modal_button(
                "±DV",
                title="Adjust Drain Value Modifier",
                body="Enter the new drain code, relative to Force.",
                fields=[LabeledNumberField("DV", -50, 50, placeholder="e.g. -3")],
            )
            def adjust_dv_button(roll: SpellRoll, context: InteractionContext, dv_mod: int) -> SpellRoll:
                return replace(roll, drain_value=roll.force + dv_mod)

            menu.add_text(f"Drain roll for {record.label}")
            menu.add_edge_buttons(record.roll_result, drain_accessor)
            menu.add_adjust_dice_button(record.roll_result, drain_accessor)

        if user_id in record.roll_result.resistance_rolls.keys():
            resist_accessor = RollAccessor[SpellRoll](
                getter=lambda r: r.resistance_rolls[user_id],
                setter=lambda r, v: replace(
                    r, resistance_rolls={**r.resistance_rolls, user_id: v}
                ),
            )
            menu.add_text(f"Resistance roll for {record.label}")
            menu.add_edge_buttons(record.roll_result, resist_accessor)
            menu.add_adjust_dice_button(record.roll_result, resist_accessor)
        await context.send_as_followup(menu)

    def resistance_target(self) -> int:
        return self.cast.hits_limited

    def current_owners(self, record: MessageRecord, context: InteractionContext):
        return [record.owner_id, *self.resistance_rolls.keys()]

    def already_resisted(self) -> list[int]:
        return [*self.resistance_rolls.keys()]

    def resist(
        self, context: InteractionContext, dice: int, limit: int, pre_edge: bool
    ) -> ResistableRoll:
        if pre_edge:
            resist_roll = roll_exploding(dice, limit=limit, gremlins=0)
        else:
            resist_roll = roll_hits(dice, limit=limit, gremlins=0)
        user_id = context.interaction.user.id
        return replace(
            self, resistance_rolls={**self.resistance_rolls, user_id: resist_roll}
        )


@roll_command(
    desc="Roll to cast a spell. Check the drain code and adjust it accordingly."
)
def roll_spell(
    *,
    force: Annotated[Range[int, 1, 50], Desc("Force of the spell.")],
    cast_dice: Annotated[Range[int, 1, 99], Desc("Dice pool for spellcasting.")],
    drain_dice: Annotated[Range[int, 1, 99], Desc("Dice pool for resisting drain.")],
    drain_code: Annotated[
        Range[int, -50, 50],
        Desc("Drain value, relative to Force. e.g. `-3`"),
    ],
    limit_override: Annotated[
        Optional[Range[int, 0, 50]],
        Desc("Optional limit override (defaults to Force)."),
    ] = None,
    pre_edge: Annotated[bool, Desc("Pre-edge the binding roll.")] = False,
    opposing_pool: Annotated[
        Optional[Range[int, 0, 99]],
        Desc("Does the spell roll against an inherent pool? e.g. Object Resistance"),
    ] = None,
) -> SpellRoll:
    if pre_edge:
        cast = roll_exploding(cast_dice)
    else:
        cast = roll_hits(cast_dice, limit=limit_override or force)
    drain = roll_hits(drain_dice)
    if opposing_pool:
        opposition = roll_hits(opposing_pool)
    else:
        opposition = None

    return SpellRoll(
        force=force,
        drain_value=force + drain_code,
        cast=cast,
        drain=drain,
        opposition=opposition,
    )


@message_codec.alias("SummonResult")
@dataclass(frozen=True)
class SummonRoll(RollRecordBase):
    # Inputs
    force: int
    drain_adjust: int  # additive override applied to DV after spirit hits

    # Rolls
    summon: HitsResult  # limited by limit/force via RollResult.limit
    resist: HitsResult  # spirit resistance; dice = force
    drain: HitsResult  # drain resistance roll

    @property
    def net_hits(self) -> int:
        return self.summon.hits_limited - self.resist.hits_limited

    @property
    def succeeded(self) -> bool:
        return self.net_hits > 0

    @property
    def drain_value(self) -> int:
        return max(0, max(2, 2 * self.resist.hits_limited) + self.drain_adjust)

    @property
    def drain_taken(self) -> int:
        return max(0, self.drain_value - self.drain.hits_limited)

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return SummonRollView(self, label, context)

    @classmethod
    async def send_menu(cls, record: MessageRecord, context: InteractionContext):
        summon_accessor = RollAccessor[SummonRoll](
            getter=lambda r: r.summon, setter=lambda r, v: replace(r, summon=v)
        )
        drain_accessor = RollAccessor[SummonRoll](
            getter=lambda r: r.drain, setter=lambda r, v: replace(r, drain=v)
        )
        menu = BaseMenuView(record_id=record.message_id)
        menu.add_text(f"Summoning roll for {record.label}")
        menu.add_standard_buttons(record.roll_result, summon_accessor)

        @menu.modal_button(
            "±F",
            title="Adjust Force",
            body="Positive numbers increase the Force, negative numbers decrease it.",
            fields=[LabeledNumberField("Force", -50, 50)],
        )
        def adjust_force_button(roll: SummonRoll, context: InteractionContext, force_mod: int) -> SummonRoll:
            new_limit = (
                roll.force + force_mod
                if roll.summon.limit == roll.force
                else roll.summon.limit
            )
            return replace(
                roll,
                force=roll.force + force_mod,
                bind=roll.summon.adjust_limit(new_limit),
                resist=roll.resist.adjust_dice(force_mod),
            )

        @menu.modal_button(
            "±DV",
            title="Adjust Drain Value Modifier",
            body="Positive numbers increase the DV, negative numbers decrease it.",
            fields=[LabeledNumberField("DV", -50, 50)],
        )
        def adjust_dv_button(roll: SummonRoll, context: InteractionContext, dv_mod: int) -> SummonRoll:
            return replace(roll, drain_adjust=dv_mod)

        menu.add_text(f"Drain roll for {record.label}")
        menu.add_edge_buttons(record.roll_result, drain_accessor)
        menu.add_adjust_dice_button(record.roll_result, drain_accessor)
        await context.send_as_followup(menu)


@roll_command(desc="Roll to summon a spirit.")
def roll_summon(
    *,
    force: Annotated[Range[int, 1, 50], Desc("Force of the spirit.")],
    summon_dice: Annotated[Range[int, 1, 99], Desc("Dice pool for summoning.")],
    drain_dice: Annotated[Range[int, 1, 99], Desc("Dice pool for resisting drain.")],
    limit_override: Annotated[
        Optional[Range[int, 0, 50]],
        Desc("Optional limit (defaults to Force)."),
    ] = None,
    drain_adjust: Annotated[
        Range[int, -50, 50], Desc("Modifier applied to drain.")
    ] = 0,
    pre_edge: Annotated[bool, Desc("Pre-edge the binding roll.")] = False,
) -> SummonRoll:
    if pre_edge:
        summon = roll_exploding(summon_dice)
    else:
        summon = roll_hits(summon_dice, limit=limit_override or force)
    resist = roll_hits(force)
    drain = roll_hits(drain_dice)

    return SummonRoll(
        force=force,
        drain_adjust=drain_adjust,
        summon=summon,
        resist=resist,
        drain=drain,
    )


def _decide_color(roll_result: AlchemyCreateRoll) -> int:
    """
    Accent based on drain outcome (because that's the "did you take drain?" part),
    but still signal critical glitches.
    """
    succ = roll_result.potency > 0
    if roll_result.drain_value <= 0:
        color = 0x8888FF
    else:
        color = 0x88FF88 if succ else 0xFF8888

    # If either roll critically glitches, go red.
    if (
        roll_result.cast.glitch == Glitch.CRITICAL
        or roll_result.drain.glitch == Glitch.CRITICAL
    ):
        return 0xFF0000

    # If any roll glitches, use purple-ish (success) or red-ish (fail)
    if (
        roll_result.cast.glitch == Glitch.GLITCH
        or roll_result.drain.glitch == Glitch.GLITCH
    ):
        return 0xCC44CC if (succ or roll_result.drain_value <= 0) else 0xCC4444

    return color


class AlchemyCreateRollView(BaseRollView):
    def __init__(
        self, roll_result: AlchemyCreateRoll, label: str, context: InteractionContext
    ):
        header_txt = (
            label
            + f"\nForce {roll_result.force} (DV F{sign_int(roll_result.drain_value - roll_result.force)})"
        )
        super().__init__(header_txt, _decide_color(roll_result), context)

        # Spellcasting line: show raw hits and limited hits
        cast_line = (
            "**Alchemy:**\n"
            + roll_result.cast.render_roll_with_glitch(context)
            + "\nvs.\n"
            + roll_result.resist.render_roll_with_glitch(context)
        )
        if roll_result.potency:
            cast_line += (
                f"\nPotency: **{roll_result.potency}** | Force: {roll_result.force}"
            )
        else:
            cast_line += "\n**Attempt failed!**"

        self.add_text(cast_line)
        self.add_separator()

        # Drain line: threshold-style
        drain_line = (
            "**Drain:** \n"
            + roll_result.drain.render_roll(context)
            + f" vs. DV{roll_result.drain_value}"
            + roll_result.drain.render_glitch(context)
        )
        self.add_text(drain_line)

        # Outcome text (drain)
        if roll_result.drain_value > 0:
            outcome = (
                "Resisted Drain!"
                if roll_result.drain_succeeded
                else f"Took **{-roll_result.drain_net_hits}** Drain!"
            )
            self.add_text(outcome)

        self.add_buttons(EdgeMenuButton())


class AlchemyActivateRollView(BaseRollView):
    def __init__(
        self, roll_result: AlchemyActivateRoll, label: str, context: InteractionContext
    ):
        cast_line = roll_result.cast.render_roll_with_glitch(context)
        header_txt = (
            label
            + f"\nForce {roll_result.force} | Potency: {roll_result.potency}"
            + (
                f" | {sign_int(roll_result.practiced)} (Practiced Alchemist)"
                if roll_result.practiced != 0
                else ""
            )
            + f"\n{cast_line}"
        )
        super().__init__(header_txt, 0xCC88CC, context)

        for user_id, resist_result in roll_result.resistance_rolls.items():
            (username, avatar) = context.get_avatar(user_id)
            dice = resist_result.render_roll_with_glitch(context)
            net_hits = resist_result.hits_limited - roll_result.cast.hits_limited
            outcome = "Succeeded!" if net_hits >= 0 else "Failed!"
            txt = f"**{username}** resists:\n{dice}\n**{outcome}** ({net_hits:+d} net)"
            self.add_section(txt, avatar)

        self.add_buttons(EdgeMenuButton(), ResistButton())


class BindingRollView(BaseRollView):
    def __init__(
        self, roll_result: BindingRoll, label: str, context: InteractionContext
    ):
        header_txt = (
            label
            + f"\nForce {roll_result.force}"
            + (
                f" (DV{sign_int(roll_result.drain_adjust)})"
                if roll_result.drain_adjust != 0
                else ""
            )
            + f"\n**Binding Cost:** {roll_result.bind_cost} reagents, 1 service"
        )
        super().__init__(header_txt, roll_result.result_color, context)

        bind_line = "**Binding:**\n" + roll_result.bind.render_roll_with_glitch(context)
        self.add_text(bind_line)

        resist_line = (
            "**Spirit Resistance:**\n"
            + roll_result.resist.render_roll_with_glitch(context)
        )
        self.add_text(resist_line)

        services_changed = (
            f"Services: **{roll_result.services_in} → {roll_result.services_out}**"
        )
        if roll_result.succeeded:
            self.add_text(
                f"Bound! Net hits: **{roll_result.net_hits}**. {services_changed}"
            )
        else:
            self.add_text(f"Binding failed. {services_changed}")
        self.add_separator()

        dv_note = ""
        if roll_result.drain_adjust != 0:
            sign = "+" if roll_result.drain_adjust > 0 else ""
            dv_note = f" (adj {sign}{roll_result.drain_adjust})"

        drain_line = (
            "**Drain Resistance:**\n"
            + roll_result.drain.render_roll(context)
            + f" vs. DV{roll_result.drain_value}{dv_note}"
            + roll_result.drain.render_glitch(context)
        )
        self.add_text(drain_line)

        if roll_result.drain_taken > 0:
            self.add_text(f"Took **{roll_result.drain_taken}** Drain!")
        else:
            self.add_text("Resisted Drain!")

        self.add_separator()
        self.add_buttons(EdgeMenuButton())


class SpellRollView(BaseRollView):
    def __init__(self, roll_result: SpellRoll, label: str, context: InteractionContext):
        header_txt = (
            label
            + f"\nForce {roll_result.force} (DV F{sign_int(roll_result.drain_value - roll_result.force)})"
        )
        super().__init__(header_txt, roll_result.result_color, context)

        # Spellcasting line: show raw hits and limited hits
        cast_line = "**Spellcasting:**\n" + roll_result.cast.render_roll_with_glitch(
            context
        )
        if roll_result.opposition:
            net_hits = (
                roll_result.cast.hits_limited - roll_result.opposition.hits_limited
            )
            cast_line += (
                "\nvs.\n"
                + roll_result.opposition.render_roll_with_glitch(context)
                + f"\n**{net_hits}** net hits."
            )
        self.add_text(cast_line)
        self.add_separator()

        # Drain line: threshold-style
        drain_line = (
            "**Drain:** \n"
            + roll_result.drain.render_roll(context)
            + f" vs. DV{roll_result.drain_value}"
            + roll_result.drain.render_glitch(context)
        )
        self.add_text(drain_line)

        # Outcome text (drain)
        if roll_result.drain_value > 0:
            outcome = (
                "Resisted Drain!"
                if roll_result.drain_succeeded
                else f"Took **{-roll_result.drain_net_hits}** Drain!"
            )
            self.add_text(outcome)

        self.add_separator()

        for user_id, resist_result in roll_result.resistance_rolls.items():
            (username, avatar) = context.get_avatar(user_id)
            dice = resist_result.render_roll_with_glitch(context)
            net_hits = resist_result.hits_limited - roll_result.cast.hits_limited
            outcome = "Succeeded!" if net_hits >= 0 else "Failed!"
            txt = f"**{username}** resists:\n{dice}\n**{outcome}** ({net_hits:+d} net)"
            self.add_section(txt, avatar)

        if roll_result.opposition:
            self.add_buttons(EdgeMenuButton())
        else:
            self.add_buttons(EdgeMenuButton(), ResistButton())


class SummonRollView(BaseRollView):
    def __init__(
        self, roll_result: SummonRoll, label: str, context: InteractionContext
    ):
        header_txt = (
            label
            + f"\nForce {roll_result.force}"
            + (
                f" (DV{sign_int(roll_result.drain_adjust)}"
                if roll_result.drain_adjust != 0
                else ""
            )
        )
        super().__init__(header_txt, self.result_color(roll_result), context)

        summon_line = "**Summoning:**\n" + roll_result.summon.render_roll_with_glitch(
            context
        )
        self.add_text(summon_line)

        resist_line = (
            "**Spirit Resistance:**\n"
            + roll_result.resist.render_roll_with_glitch(context)
        )
        self.add_text(resist_line)

        if roll_result.succeeded:
            self.add_text(f"Summoned! Services: **{roll_result.net_hits}**")
        else:
            self.add_text("Summoning failed.")
        self.add_separator()

        dv_note = ""
        if roll_result.drain_adjust != 0:
            sign = "+" if roll_result.drain_adjust > 0 else ""
            dv_note = f" (adj {sign}{roll_result.drain_adjust})"

        drain_line = (
            "**Drain Resistance:**\n"
            + roll_result.drain.render_roll(context)
            + f" vs. DV{roll_result.drain_value}{dv_note}"
            + roll_result.drain.render_glitch(context)
        )
        self.add_text(drain_line)

        if roll_result.drain_taken > 0:
            self.add_text(f"Took **{roll_result.drain_taken}** Drain!")
        else:
            self.add_text("Resisted Drain!")

        self.add_buttons(EdgeMenuButton())

    @staticmethod
    def result_color(result: SummonRoll) -> int:
        if (
            result.summon.glitch == Glitch.CRITICAL
            or result.resist.glitch == Glitch.CRITICAL
            or result.drain.glitch == Glitch.CRITICAL
        ):
            return 0xFF0000

        if (
            result.summon.glitch == Glitch.GLITCH
            or result.resist.glitch == Glitch.GLITCH
            or result.drain.glitch == Glitch.GLITCH
        ):
            return 0xCC44CC if result.succeeded else 0xCC4444

        if result.succeeded:
            return 0x88FF88
        return 0xFF8888 if result.drain_taken > 0 else 0xFFAA66
