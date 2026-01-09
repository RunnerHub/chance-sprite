# basic.py
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta, datetime, timezone
from typing import Optional, Annotated

from boltons.cacheutils import cachedproperty
from discord import app_commands
from discord import ui

from chance_sprite.result_types import HitsResult
from chance_sprite.roller import roll_hits, roll_exploding
from ..fungen import Desc, roll_command
from ..message_cache import message_codec
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..rollui.commonui import build_header, RollAccessor
from ..rollui.edge_menu_persist import EdgeMenuButton
from ..rollui.generic_edge_menu import GenericEdgeMenu
from ..sprite_context import InteractionContext
from ..sprite_utils import humanize_timedelta, color_by_net_hits


class ThresholdView(ui.LayoutView):
    def __init__(self, roll_result: ThresholdRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        container = build_header(EdgeMenuButton(), label, color_by_net_hits(roll_result.net_hits))

        dice = roll_result.result.render_roll(context)
        if roll_result.threshold:
            dice += f" vs ({roll_result.threshold})"
        glitch = roll_result.result.render_glitch(context)
        if glitch:
            dice += "\n" + glitch
        container.add_item(ui.TextDisplay(dice))

        if roll_result.threshold > 0:
            outcome = "Succeeded!" if roll_result.succeeded else "Failed!"
            container.add_item(ui.TextDisplay(f"**{outcome}** ({roll_result.net_hits:+d} net)"))

        self.add_item(container)


@message_codec.alias("SimpleRoll")
@message_codec.alias("ThresholdResult")
@dataclass(frozen=True)
class ThresholdRoll(RollRecordBase):
    result: HitsResult
    threshold: int = 0

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

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return ThresholdView(self, label, context)

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        result_accessor = RollAccessor[ThresholdRoll](getter=lambda r: r.result,
                                                      setter=lambda r, v: replace(r, result=v))
        menu = GenericEdgeMenu(f"Edge for {record.label}:", result_accessor, record.message_id, interaction)
        await interaction.send_as_followup(menu)


@roll_command(desc="Roll some d6s, Shadowrun-style.")
def roll_simple(*,
                dice: Annotated[
                    app_commands.Range[int, 1, 99], Desc("Number of dice (1-99).")],
                threshold: Annotated[
                    app_commands.Range[int, 0, 99], Desc("Threshold to reach (0 if none).")],
                limit: Annotated[
                    app_commands.Range[int, 0, 99], Desc("The limit associated with the roll (0 if none).")],
                gremlins: Annotated[
                    app_commands.Range[int, 0, 4], Desc("Reduces 1s needed to glitch. Gremlins, Social Stress, etc.")]
                = 0,
                pre_edge: Annotated[
                    bool, Desc("Pre-edge Break the Limit.")]
                = False,
                ):
    if pre_edge:
        roll = roll_exploding(dice, gremlins=gremlins)
    else:
        roll = roll_hits(dice, limit=limit, gremlins=gremlins)
    return ThresholdRoll(result=roll, threshold=threshold)


class ExtendedRollView(ui.LayoutView):
    def __init__(self, roll_result: ExtendedRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        accent = 0x88FF88 if roll_result.succeeded else 0xFF8888
        menu_button = EdgeMenuButton()
        container = build_header(menu_button, label, accent)

        container.add_item(
            ui.TextDisplay(
                f"Extended test: start **{roll_result.start_dice}** dice, threshold **{roll_result.threshold}**, max **{roll_result.max_iters}** roll(s)\n"
            )
        )

        container.add_item(ui.Separator())

        # Pack iterations into as few TextDisplays as possible to respect the ~30 component limit.
        blocks: list[str] = []
        prev = 0
        for it in roll_result.iterations:
            blocks.append(
                f"`{it.roll.dice}d6` {it.roll.render_dice(context)} [{prev}+**{it.roll.hits_limited}**=**{it.cumulative_hits}**]"
            )
            prev = it.cumulative_hits

        # Split into chunks
        chunk = ""
        for b in blocks:
            candidate = (chunk + "\n" + b).strip() if chunk else b
            if len(candidate) > 1800:  # keep headroom
                container.add_item(ui.TextDisplay(chunk))
                chunk = b
            else:
                chunk = candidate

        if chunk:
            container.add_item(ui.TextDisplay(chunk))

        container.add_item(ui.Separator())
        container.add_item(
            ui.TextDisplay(
                f"Result: **{'Succeeded' if roll_result.succeeded else 'Failed'}** after **{roll_result.iters_used}** interval{"s" if roll_result.iters_used != 1 else ""} with {roll_result.final_hits} total hits (**{roll_result.final_hits - roll_result.threshold}** net)"
            )
        )

        self.add_item(container)


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
        return self.final_hits > self.threshold

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
    async def send_edge_menu(cls, record: MessageRecord, context: InteractionContext):
        pass


@roll_command(desc="Extended roll: repeated tests with shrinking dice pool until a threshold is met.")
def roll_extended(*,
                  dice: Annotated[
                      app_commands.Range[int, 1, 99], Desc("Starting dice pool (1-99).")],
                  threshold: Annotated[
                      app_commands.Range[int, 1, 99], Desc("Total hits needed (>=1).")],
                  max_iters: Annotated[
                      app_commands.Range[int, 1, 99], Desc("Maximum number of rolls (1-99).")]
                  = 10,
                  limit: Annotated[
                      app_commands.Range[int, 0, 99], Desc("Limit applicable to each roll.")]
                  = 0,
                  gremlins: Annotated[
                      Optional[app_commands.Range[int, 1, 99]], Desc("Reduce the number of 1s required for a glitch.")]
                  = None
                  ) -> ExtendedRoll:
    iterations: list[ExtendedIteration] = []
    cumulative = 0

    for i in range(1, max_iters + 1):
        pool = dice - (i - 1)
        if pool < 1:
            break

        r = roll_hits(pool, limit=limit, gremlins=gremlins)
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
        gremlins=gremlins
    )


class OpposedRollView(ui.LayoutView):
    def __init__(self, roll_result: OpposedRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)

        menu_button = EdgeMenuButton()
        container = build_header(menu_button, label, color_by_net_hits(roll_result.net_hits))

        # Initiator block
        container.add_item(ui.TextDisplay(
            f"**Initiator:**\n{roll_result.initiator.render_roll_with_glitch(context)}"))

        container.add_item(ui.Separator())
        # Defender block
        container.add_item(ui.TextDisplay(
            f"**Defender:**\n{roll_result.defender.render_roll_with_glitch(context)}"))

        net = roll_result.net_hits
        # Outcome
        container.add_item(ui.Separator())
        if net == 0:
            container.add_item(ui.TextDisplay("Tie; Defender wins. (0 net hits)"))
        else:
            container.add_item(ui.TextDisplay(f"{roll_result.outcome} with **{net:+d}** net hits"))

        self.add_item(container)


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
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        result_accessor = RollAccessor[OpposedRoll](getter=lambda r: r.initiator,
                                                    setter=lambda r, v: replace(r, initiator=v))
        menu = GenericEdgeMenu(f"Edge initiator for {record.label}?", result_accessor, record.message_id, interaction)
        await interaction.send_as_followup(menu)


@roll_command(desc="Opposed roll: initiator vs defender. Defender wins ties.")
def roll_opposed(*,
                 initiator_dice: Annotated[
                     app_commands.Range[int, 1, 99], Desc("Initiator dice pool (1-99).")],
                 defender_dice: Annotated[
                     app_commands.Range[int, 1, 99], Desc("Defender dice pool (1-99).")],
                 initiator_limit: Annotated[
                     app_commands.Range[int, 0, 99], Desc("Initiator's limit, accuracy, etc.")],
                 defender_limit: Annotated[
                     app_commands.Range[int, 0, 99], Desc("Defender's limit, if applicable.")]
                 = 0,
                 initiator_gremlins: Annotated[
                     app_commands.Range[int, 0, 4], Desc("Reduce the number of 1s required for a glitch.")]
                 = 0,
                 defender_gremlins: Annotated[
                     app_commands.Range[int, 0, 4], Desc("Reduce the number of 1s required for a glitch.")]
                 = 0,
                 pre_edge: Annotated[
                     bool, Desc("Initiator can pre-edge: Break the Limit.")]
                 = False,
                 ) -> OpposedRoll:
    if pre_edge:
        initiator = roll_exploding(initiator_dice, gremlins=initiator_gremlins)
    else:
        initiator = roll_hits(initiator_dice, limit=initiator_limit, gremlins=initiator_gremlins)
    defender = roll_hits(defender_dice, limit=defender_limit, gremlins=defender_gremlins)
    return OpposedRoll(initiator=initiator, defender=defender)


class AvailabilityRollView(ui.LayoutView):
    def __init__(self, roll_result: AvailabilityRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        costdetail = label
        if roll_result.base_delivery_time:
            label += f"\n-# Cost: {roll_result.cost}; base delivery time: {humanize_timedelta(roll_result.base_delivery_time)}"
        menu_button = EdgeMenuButton()
        container = build_header(menu_button, label, color_by_net_hits(roll_result.net_hits))

        # Initiator block
        container.add_item(ui.TextDisplay(
            f"**Negotiation:**\n{roll_result.initiator.render_roll_with_glitch(context)}"))

        container.add_item(ui.Separator())
        # Defender block
        container.add_item(ui.TextDisplay(
            f"**Availability:**\n{roll_result.defender.render_roll_with_glitch(context)}"))

        # Outcome
        container.add_item(ui.Separator())
        outcome = ""
        if roll_result.net_hits < 0:
            outcome += f"**Failed** by {abs(roll_result.net_hits)}: item not acquired."
        else:
            if roll_result.net_hits == 0:
                outcome += f"**Tie**; delivered in double time."
            elif roll_result.net_hits == 1:
                outcome += "**Success**: delivered in standard time"
            else:
                outcome += f"**Success**: delivered in **1/{roll_result.net_hits}** standard time"
            if roll_result.adjusted_delivery_time:
                eta = datetime.now(timezone.utc) + roll_result.adjusted_delivery_time
                outcome += f": {humanize_timedelta(roll_result.adjusted_delivery_time)}\n <t:{int(eta.timestamp())}:f> (<t:{int(eta.timestamp())}:R>)"

        container.add_item(ui.TextDisplay(outcome))

        @property
        def outcome(self) -> str:
            if self.net_hits < 0:
                return f"Failed: item not acquired"
            elif self.net_hits == 0:
                return f"Tie (delivered in double time)"
            elif self.net_hits == 1:
                return f"Success: delivered in standard time"
            else:
                return f"Success: delivered in 1/{self.net_hits} standard time"

        self.add_item(container)


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
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        result_accessor = RollAccessor[OpposedRoll](getter=lambda r: r.initiator,
                                                    setter=lambda r, v: replace(r, initiator=v))
        menu = GenericEdgeMenu(f"Edge initiator for {record.label}?", result_accessor, record.message_id, interaction)
        await interaction.send_as_followup(menu)


@roll_command(desc="Availability roll: for gear acquisition.")
def roll_availability(*,
                      acquisition_dice: Annotated[
                          app_commands.Range[int, 1, 99], Desc("Dice for the negotiation test.")],
                      availability: Annotated[app_commands.Range[int, 0, 99], Desc(
                          "Availability of the desired item (opposes your roll).")],
                      social_limit: Annotated[
                          app_commands.Range[int, 0, 99], Desc("Social limit if applicable.")]
                      = 0,
                      cost: Annotated[
                          Optional[app_commands.Range[int, 0, 1000000]], Desc("Cost of the item in nuyen.")]
                      = None,
                      street_cred_mod: Annotated[
                          app_commands.Range[int, -99, 99],
                          Desc("-1 for every 10 street cred (optional, you can just factor it in yourself).")]
                      = 0,
                      pre_edge: Annotated[
                          bool, Desc("Pre-edge the availability roll.")]
                      = False,
                      ) -> AvailabilityRoll:
    if pre_edge:
        initiator = roll_exploding(acquisition_dice)
    else:
        initiator = roll_hits(acquisition_dice, limit=social_limit)
    defender = roll_hits(availability + street_cred_mod)
    return AvailabilityRoll(initiator=initiator, defender=defender, cost=cost)
