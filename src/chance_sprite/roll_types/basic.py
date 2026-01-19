# basic.py
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, override

from boltons.cacheutils import cachedproperty
from discord import app_commands, ui

from chance_sprite.result_types import HitsResult
from chance_sprite.roller import (
    roll_exploding,
    roll_hits,
)

from ..fungen import Desc, roll_command
from ..message_cache import message_codec
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import ResistableRoll, RollRecordBase
from ..rollui.base_roll_view import BaseMenuView, BaseRollView
from ..rollui.roll_accessor import DirectRollAccessor
from ..rollui.roll_view_persist import EdgeMenuButton, ResistButton
from ..sprite_context import InteractionContext
from ..sprite_utils import color_by_net_hits, humanize_timedelta, plural_s


class ThresholdView(BaseRollView):
    def __init__(
        self, roll_result: ThresholdRoll, label: str, context: InteractionContext
    ):
        dice = roll_result.result.render_roll(context)
        if roll_result.threshold:
            dice += f" vs ({roll_result.threshold})"
        glitch = roll_result.result.render_glitch(context)
        if glitch:
            dice += "\n" + glitch

        outcome_txt = ""
        if roll_result.threshold > 0:
            outcome = "Succeeded!" if roll_result.succeeded else "Failed!"
            outcome_txt = f"**{outcome}** ({roll_result.net_hits:+d} net)"

        super().__init__(
            f"{label}\n{dice}\n{outcome_txt}",
            color_by_net_hits(roll_result.net_hits),
            context,
        )

        for user_id, resist_result in roll_result.resistance_rolls.items():
            (username, avatar) = context.get_avatar(user_id)
            dice = resist_result.render_roll_with_glitch(context)
            net_hits = resist_result.hits_limited - roll_result.result.hits_limited
            outcome = "Succeeded!" if net_hits >= 0 else "Failed!"
            txt = f"**{username}** resists:\n{dice}\n**{outcome}** ({net_hits:+d} net)"
            self.add_section(txt, avatar)

        if roll_result.resistable:
            self.add_buttons(EdgeMenuButton(), ResistButton())
        else:
            self.add_buttons(EdgeMenuButton())


@message_codec.alias("SimpleRoll")
@message_codec.alias("ThresholdResult")
@dataclass(frozen=True)
class ThresholdRoll(ResistableRoll):
    result: HitsResult
    threshold: int = 0
    resistance_rolls: dict[int, HitsResult] = field(default_factory=dict)

    @property
    def succeeded(self) -> Optional[bool]:
        if self.threshold <= 0:
            return None
        return self.result.hits_limited >= self.threshold

    @property
    def net_hits(self) -> int:
        if self.threshold <= 0:
            return 0
        return self.result.hits_limited - self.threshold

    @override
    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return ThresholdView(self, label, context)

    @classmethod
    async def send_menu(
        cls, record: MessageRecord[ThresholdRoll], context: InteractionContext
    ):
        user_id = context.interaction.user.id
        menu = BaseMenuView(record_id=record.message_id)
        if user_id == record.owner_id:
            menu.add_text("Threshold roll:")
            result_accessor = DirectRollAccessor[ThresholdRoll](
                getter=lambda r: r.result,
                setter=lambda r, v: replace(r, result=v),
            )
            menu.add_standard_buttons(record.roll_result, result_accessor)

        if user_id in record.roll_result.resistance_rolls.keys():
            result_accessor = DirectRollAccessor[ThresholdRoll](
                getter=lambda r: r.resistance_rolls[user_id],
                setter=lambda r, v: replace(
                    r, resistance_rolls={**r.resistance_rolls, user_id: v}
                ),
            )
            menu.add_text("Resistance roll:")
            menu.add_standard_buttons(record.roll_result, result_accessor)
        await context.send_as_followup(menu)

    def resistance_target(self) -> int:
        return self.result.hits_limited

    def current_owners(self, record: MessageRecord, context: InteractionContext):
        return [record.owner_id, *self.resistance_rolls.keys()]

    def resist(
        self, record: MessageRecord, context: InteractionContext, dice: int
    ) -> ResistableRoll:
        resist_roll = roll_hits(dice, limit=0, gremlins=0)
        user_id = context.interaction.user.id
        return replace(
            self, resistance_rolls={**self.resistance_rolls, user_id: resist_roll}
        )

    def already_resisted(self) -> list[int]:
        return [*self.resistance_rolls.keys()]


@roll_command(desc="Roll some d6s, Shadowrun-style.")
def roll_simple(
    *,
    dice: Annotated[app_commands.Range[int, 1, 99], Desc("Number of dice (1-99).")],
    threshold: Annotated[
        app_commands.Range[int, 0, 99], Desc("Threshold to reach (0 if none).")
    ],
    limit: Annotated[
        app_commands.Range[int, 0, 99],
        Desc("The limit associated with the roll (0 if none)."),
    ],
    gremlins: Annotated[
        app_commands.Range[int, 0, 4],
        Desc("Reduces 1s needed to glitch. Gremlins, Social Stress, etc."),
    ] = 0,
    pre_edge: Annotated[bool, Desc("Pre-edge Break the Limit.")] = False,
    resistable: Annotated[
        bool, Desc("Can others attempt to resist this roll?")
    ] = False,
) -> ThresholdRoll:
    if pre_edge:
        roll = roll_exploding(dice, gremlins=gremlins)
    else:
        roll = roll_hits(dice, limit=limit, gremlins=gremlins)
    return ThresholdRoll(result=roll, threshold=threshold, resistable=resistable)


class ExtendedRollView(BaseRollView):
    def __init__(
        self, roll_result: ExtendedRoll, label: str, context: InteractionContext
    ):
        accent = 0x88FF88 if roll_result.succeeded else 0xFF8888
        super().__init__(label, accent, context)

        self.add_text(
            f"Extended test: start **{roll_result.start_dice}** dice, threshold **{roll_result.threshold}**, max **{roll_result.max_iters}** roll(s)\n"
        )

        self.add_separator()

        # Pack iterations into as few TextDisplays as possible to respect the ~30 component limit.
        blocks: list[str] = []
        prev = 0
        for it in roll_result.iterations:
            blocks.append(
                f"`{it.roll.dice}d6` {it.roll.render_dice(context)} [{prev}+**{it.roll.hits_limited}**=**{it.cumulative_hits}**]"
            )
            prev = it.cumulative_hits

        self.add_long_text(blocks)
        self.add_separator()
        self.add_text(
            f"Result: **{'Succeeded' if roll_result.succeeded else 'Failed'}** after **{roll_result.iters_used}** interval{plural_s(roll_result.iters_used)} with {roll_result.final_hits} total hit{plural_s(roll_result.final_hits)} (**{roll_result.final_hits - roll_result.threshold}** net)"
        )


@dataclass(frozen=True)
class ExtendedIteration:
    n: int
    roll: HitsResult
    cumulative_hits: int


@message_codec.alias("ExtendedResult")
@dataclass(frozen=True)
class ExtendedRoll(RollRecordBase):
    start_dice: int
    threshold: int
    max_iters: int
    iterations: tuple[ExtendedIteration, ...]
    limit: int
    gremlins: int

    @property
    def succeeded(self):
        return self.final_hits >= self.threshold

    @cachedproperty
    def final_hits(self):
        if self.iterations:
            return self.iterations[-1].cumulative_hits
        else:
            return 0

    @cachedproperty
    def iters_used(self):
        return len(self.iterations)

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return ExtendedRollView(self, label, context)

    @classmethod
    async def send_menu(cls, record: MessageRecord, context: InteractionContext):
        pass


@roll_command(
    desc="Extended roll: repeated tests with shrinking dice pool until a threshold is met."
)
def roll_extended(
    *,
    dice: Annotated[app_commands.Range[int, 1, 99], Desc("Starting dice pool (1-99).")],
    threshold: Annotated[
        app_commands.Range[int, 1, 99], Desc("Total hits needed (>=1).")
    ],
    max_iters: Annotated[
        app_commands.Range[int, 1, 99], Desc("Maximum number of rolls (1-99).")
    ] = 10,
    limit: Annotated[
        app_commands.Range[int, 0, 99], Desc("Limit applicable to each roll.")
    ] = 0,
    gremlins: Annotated[
        Optional[app_commands.Range[int, 0, 4]],
        Desc("Reduce the number of 1s required for a glitch."),
    ] = 0,
) -> ExtendedRoll:
    iterations: list[ExtendedIteration] = []
    cumulative = 0

    for i in range(1, max_iters + 1):
        pool = dice - (i - 1)
        if pool < 1:
            break

        r = roll_hits(pool, limit=limit, gremlins=gremlins or 0)
        cumulative += r.hits_limited
        iterations.append(ExtendedIteration(n=i, roll=r, cumulative_hits=cumulative))

        if cumulative >= threshold:
            break

    return ExtendedRoll(
        start_dice=dice,
        threshold=threshold,
        max_iters=max_iters,
        iterations=tuple(iterations),
        limit=limit,
        gremlins=gremlins,
    )


class OpposedRollView(BaseRollView):
    def __init__(
        self, roll_result: OpposedRoll, label: str, context: InteractionContext
    ):
        super().__init__(label, color_by_net_hits(roll_result.net_hits), context)

        # Initiator block
        self.add_text(
            f"**Initiator:**\n{roll_result.initiator.render_roll_with_glitch(context)}"
        )

        self.add_separator()
        # Defender block
        self.add_text(
            f"**Defender:**\n{roll_result.defender.render_roll_with_glitch(context)}"
        )

        net = roll_result.net_hits
        # Outcome
        self.add_separator()
        if net == 0:
            self.add_text("Tie; Defender wins. (0 net hits)")
        else:
            self.add_text(f"{roll_result.outcome} with **{net:+d}** net hits")

        self.add_buttons(EdgeMenuButton())


@message_codec.alias("OpposedResult")
@dataclass(frozen=True)
class OpposedRoll(RollRecordBase):
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

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return OpposedRollView(self, label, context)

    @classmethod
    async def send_menu(cls, record: MessageRecord, context: InteractionContext):
        initiator_accessor = DirectRollAccessor[OpposedRoll](
            getter=lambda r: r.initiator, setter=lambda r, v: replace(r, initiator=v)
        )
        defender_accessor = DirectRollAccessor[OpposedRoll](
            getter=lambda r: r.defender, setter=lambda r, v: replace(r, defender=v)
        )
        menu = BaseMenuView(record_id=record.message_id)
        menu.add_text("Initiator roll:")
        menu.add_standard_buttons(record.roll_result, initiator_accessor)
        menu.add_text("Defender roll:")
        menu.add_standard_buttons(record.roll_result, defender_accessor)
        await context.send_as_followup(menu)


@roll_command(desc="Opposed roll: initiator vs defender. Defender wins ties.")
def roll_opposed(
    *,
    initiator_dice: Annotated[
        app_commands.Range[int, 1, 99], Desc("Initiator dice pool (1-99).")
    ],
    defender_dice: Annotated[
        app_commands.Range[int, 1, 99], Desc("Defender dice pool (1-99).")
    ],
    initiator_limit: Annotated[
        app_commands.Range[int, 0, 99], Desc("Initiator's limit, accuracy, etc.")
    ],
    defender_limit: Annotated[
        app_commands.Range[int, 0, 99], Desc("Defender's limit, if applicable.")
    ] = 0,
    initiator_gremlins: Annotated[
        app_commands.Range[int, 0, 4],
        Desc("Reduce the number of 1s required for a glitch."),
    ] = 0,
    defender_gremlins: Annotated[
        app_commands.Range[int, 0, 4],
        Desc("Reduce the number of 1s required for a glitch."),
    ] = 0,
    pre_edge: Annotated[bool, Desc("Initiator can pre-edge: Break the Limit.")] = False,
) -> OpposedRoll:
    if pre_edge:
        initiator = roll_exploding(initiator_dice, gremlins=initiator_gremlins)
    else:
        initiator = roll_hits(
            initiator_dice, limit=initiator_limit, gremlins=initiator_gremlins
        )
    defender = roll_hits(
        defender_dice, limit=defender_limit, gremlins=defender_gremlins
    )
    return OpposedRoll(initiator=initiator, defender=defender)


class AvailabilityRollView(BaseRollView):
    def __init__(
        self, roll_result: AvailabilityRoll, label: str, context: InteractionContext
    ):
        if roll_result.base_delivery_time:
            label += f"\n-# Cost: {roll_result.cost}; base delivery time: {humanize_timedelta(roll_result.base_delivery_time)}"
        super().__init__(label, color_by_net_hits(roll_result.net_hits), context)

        # Initiator block
        self.add_text(
            f"**Negotiation:**\n{roll_result.initiator.render_roll_with_glitch(context)}"
        )

        self.add_separator()
        # Defender block
        self.add_text(
            f"**Availability:**\n{roll_result.defender.render_roll_with_glitch(context)}"
        )

        # Outcome
        self.add_separator()
        outcome_string = ""
        if roll_result.net_hits < 0:
            outcome_string += (
                f"**Failed** by {abs(roll_result.net_hits)}: item not acquired."
            )
        else:
            if roll_result.net_hits == 0:
                outcome_string += "**Tie**; delivered in double time."
            elif roll_result.net_hits == 1:
                outcome_string += "**Success**: delivered in standard time"
            else:
                outcome_string += f"**Success**: delivered in **1/{roll_result.net_hits}** standard time"
            if roll_result.adjusted_delivery_time:
                eta = datetime.now(timezone.utc) + roll_result.adjusted_delivery_time
                outcome_string += f": {humanize_timedelta(roll_result.adjusted_delivery_time)}\n <t:{int(eta.timestamp())}:f> (<t:{int(eta.timestamp())}:R>)"

        self.add_text(outcome_string)

        self.add_buttons(EdgeMenuButton())


@message_codec.alias("OpposedResult")
@dataclass(frozen=True)
class AvailabilityRoll(RollRecordBase):
    initiator: HitsResult
    defender: HitsResult
    cost: int | None

    @property
    def net_hits(self) -> int:
        return self.initiator.hits_limited - self.defender.hits_limited

    @property
    def delivery_time_multiplier(self) -> float | None:
        if self.net_hits < 0:
            return None
        elif self.net_hits == 0:
            return 2
        else:
            return 1 / self.net_hits

    @property
    def base_delivery_time(self) -> timedelta | None:
        if not self.cost:
            return None
        elif self.cost <= 100:
            return timedelta(hours=6)
        elif self.cost <= 1000:
            return timedelta(days=1)
        elif self.cost <= 10000:
            return timedelta(days=2)
        elif self.cost <= 100000:
            return timedelta(weeks=1)
        else:
            return timedelta(weeks=4)

    @property
    def adjusted_delivery_time(self):
        if self.base_delivery_time and self.delivery_time_multiplier:
            return self.base_delivery_time * self.delivery_time_multiplier
        return None

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return AvailabilityRollView(self, label, context)

    @classmethod
    async def send_menu(cls, record: MessageRecord, context: InteractionContext):
        initiator_accessor = DirectRollAccessor[AvailabilityRoll](
            getter=lambda r: r.initiator, setter=lambda r, v: replace(r, initiator=v)
        )
        defender_accessor = DirectRollAccessor[AvailabilityRoll](
            getter=lambda r: r.defender, setter=lambda r, v: replace(r, defender=v)
        )
        menu = BaseMenuView(record_id=record.message_id)
        menu.add_text("Initiator roll:")
        menu.add_standard_buttons(record.roll_result, initiator_accessor)
        menu.add_text("Defender roll:")
        menu.add_standard_buttons(record.roll_result, defender_accessor)
        await context.send_as_followup(menu)


@roll_command(desc="Availability roll: for gear acquisition.")
def roll_availability(
    *,
    acquisition_dice: Annotated[
        app_commands.Range[int, 1, 99], Desc("Dice for the negotiation test.")
    ],
    availability: Annotated[
        app_commands.Range[int, 0, 99],
        Desc("Availability of the desired item (opposes your roll)."),
    ],
    social_limit: Annotated[
        app_commands.Range[int, 0, 99], Desc("Social limit if applicable.")
    ] = 0,
    cost: Annotated[
        Optional[app_commands.Range[int, 0, 1000000]],
        Desc("Cost of the item in nuyen."),
    ] = None,
    street_cred_mod: Annotated[
        app_commands.Range[int, -99, 99],
        Desc(
            "-1 for every 10 street cred (optional, you can just factor it in yourself)."
        ),
    ] = 0,
    pre_edge: Annotated[bool, Desc("Pre-edge the availability roll.")] = False,
) -> AvailabilityRoll:
    if pre_edge:
        initiator = roll_exploding(acquisition_dice)
    else:
        initiator = roll_hits(acquisition_dice, limit=social_limit)
    defender = roll_hits(availability + street_cred_mod)
    return AvailabilityRoll(initiator=initiator, defender=defender, cost=cost)
