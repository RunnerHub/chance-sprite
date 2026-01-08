# $FILE_NAME$
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Optional, Self

from discord import ui, app_commands, Interaction

from chance_sprite.message_cache import message_codec
from chance_sprite.message_cache.message_record import MessageRecord
from chance_sprite.message_cache.roll_record_base import RollRecordBase
from chance_sprite.result_types import Glitch, HitsResult
from chance_sprite.roller import roll_hits
from chance_sprite.rollui.autocomplete import build_args_autocomplete_suggestions, ArgSpec
from chance_sprite.rollui.commonui import build_header, RollAccessor
from chance_sprite.rollui.edge_menu_persist import EdgeMenuButton
from chance_sprite.rollui.generic_edge_menu import GenericEdgeMenu
from chance_sprite.sprite_context import InteractionContext, ClientContext

log = logging.getLogger(__name__)


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
    if roll_result.cast.glitch == Glitch.CRITICAL or roll_result.drain.glitch == Glitch.CRITICAL:
        return 0xFF0000

    # If any roll glitches, use purple-ish (success) or red-ish (fail)
    if roll_result.cast.glitch == Glitch.GLITCH or roll_result.drain.glitch == Glitch.GLITCH:
        return 0xCC44CC if (succ or roll_result.drain_value <= 0) else 0xCC4444

    return color


class AlchemyCreateRollView(ui.LayoutView):
    def __init__(self, roll_result: AlchemyCreateRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        container = build_header(EdgeMenuButton(), label + f"\nForce {roll_result.force}",
                                 _decide_color(roll_result))

        # Spellcasting line: show raw hits and limited hits
        cast_line = (
                f"**Alchemy:**\n"
                + roll_result.cast.render_roll_with_glitch(context)
                + f"\nvs.\n"
                + roll_result.resist.render_roll_with_glitch(context)
        )
        if roll_result.potency:
            cast_line += f"\nPotency: **{roll_result.potency}**"
        else:
            cast_line += f"\n**Attempt failed!**"

        cast_section = ui.TextDisplay(cast_line)
        container.add_item(cast_section)
        container.add_item(ui.Separator())

        # Drain line: threshold-style
        drain_line = (
                f"**Drain:** \n"
                + roll_result.drain.render_roll(context) + f" vs. DV{roll_result.drain_value}"
                + roll_result.drain.render_glitch(context)
        )
        container.add_item(ui.TextDisplay(drain_line))

        # Outcome text (drain)
        if roll_result.drain_value > 0:
            outcome = "Resisted Drain!" if roll_result.drain_succeeded else f"Took **{-roll_result.drain_net_hits}** Drain!"
            container.add_item(ui.TextDisplay(outcome))

        self.add_item(container)


class BindingRollView(ui.LayoutView):
    def __init__(self, roll_result: BindingRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        menu_button = EdgeMenuButton()
        container = build_header(menu_button,
                                 label + f"\nForce {roll_result.force} | **Binding Cost:** {roll_result.bind_cost} reagents, 1 service",
                                 roll_result.result_color)

        bind_line = "**Binding:**\n" + roll_result.bind.render_roll_with_glitch(context)
        container.add_item(ui.TextDisplay(bind_line))

        resist_line = f"**Spirit Resistance:**\n" + roll_result.resist.render_roll_with_glitch(
            context)
        container.add_item(ui.TextDisplay(resist_line))

        services_changed = f"Services: **{roll_result.services_in} → {roll_result.services_out}**"
        if roll_result.succeeded:
            container.add_item(ui.TextDisplay(f"Bound! Net hits: **{roll_result.net_hits}**. {services_changed}"))
        else:
            container.add_item(ui.TextDisplay(f"Binding failed. {services_changed}"))
        container.add_item(ui.Separator())

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
        container.add_item(ui.TextDisplay(drain_line))

        if roll_result.drain_taken > 0:
            container.add_item(ui.TextDisplay(f"Took **{roll_result.drain_taken}** Drain!"))
        else:
            container.add_item(ui.TextDisplay("Resisted Drain!"))

        self.add_item(container)


class SpellRollView(ui.LayoutView):
    def __init__(self, roll_result: SpellRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        container = build_header(EdgeMenuButton(), label + f"\nForce {roll_result.force}", roll_result.result_color)

        # Spellcasting line: show raw hits and limited hits
        cast_line = (
                f"**Spellcasting:**\n"
                + roll_result.cast.render_roll_with_glitch(context)
        )
        container.add_item(ui.TextDisplay(cast_line))
        container.add_item(ui.Separator())

        # Drain line: threshold-style
        drain_line = (
                f"**Drain:** \n"
                + roll_result.drain.render_roll(context) + f" vs. DV{roll_result.drain_value}"
                + roll_result.drain.render_glitch(context)
        )
        container.add_item(ui.TextDisplay(drain_line))

        # Outcome text (drain)
        if roll_result.drain_value > 0:
            outcome = "Resisted Drain!" if roll_result.drain_succeeded else f"Took **{-roll_result.drain_net_hits}** Drain!"
            container.add_item(ui.TextDisplay(outcome))

        self.add_item(container)


class SummonRollView(ui.LayoutView):
    def __init__(self, roll_result: SummonRoll, label: str, context: InteractionContext):
        super().__init__(timeout=None)
        container = build_header(EdgeMenuButton(), label + f"\nForce {roll_result.force}",
                                 self.result_color(roll_result))

        summon_line = "**Summoning:**\n" + roll_result.summon.render_roll_with_glitch(context)
        container.add_item(ui.TextDisplay(summon_line))

        resist_line = f"**Spirit Resistance:**\n" + roll_result.resist.render_roll_with_glitch(context)
        container.add_item(ui.TextDisplay(resist_line))

        if roll_result.succeeded:
            container.add_item(ui.TextDisplay(f"Summoned! Services: **{roll_result.net_hits}**"))
        else:
            container.add_item(ui.TextDisplay(f"Summoning failed."))
        container.add_item(ui.Separator())

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
        container.add_item(ui.TextDisplay(drain_line))

        if roll_result.drain_taken > 0:
            container.add_item(ui.TextDisplay(f"Took **{roll_result.drain_taken}** Drain!"))
        else:
            container.add_item(ui.TextDisplay("Resisted Drain!"))

        self.add_item(container)

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


@dataclass(frozen=True)
class AlchemyCreateRoll(RollRecordBase):
    # Inputs
    force: int
    limit: int
    drain_value: int

    # Rolls
    cast: HitsResult
    resist: HitsResult
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
    def potency(self):
        return max(self.cast.hits_limited - self.resist.hits_limited, 0)

    @staticmethod
    def roll(
            *,
            force: int,
            cast_dice: int,
            drain_value: int,
            drain_dice: int,
            limit: Optional[int] = None,
    ) -> AlchemyCreateRoll:
        lim = force if limit is None else limit

        cast = roll_hits(cast_dice, limit=limit or 0)

        resist = roll_hits(force)

        drain = roll_hits(drain_dice)

        return AlchemyCreateRoll(
            force=force,
            limit=lim,
            drain_value=drain_value,
            cast=cast,
            resist=resist,
            drain=drain,
        )

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return AlchemyCreateRollView(self, label, context)

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        cast_accessor = RollAccessor[AlchemyCreateRoll](getter=lambda r: r.cast, setter=lambda r, v: replace(r, cast=v))
        edge_menu1 = GenericEdgeMenu(f"Edge Alchemy for {record.label}?", cast_accessor, record.message_id,
                                     interaction)
        await interaction.send_as_followup(edge_menu1)

        drain_accessor = RollAccessor[AlchemyCreateRoll](getter=lambda r: r.drain,
                                                         setter=lambda r, v: replace(r, drain=v))
        menu2 = GenericEdgeMenu(f"Edge Drain for {record.label}?", drain_accessor, record.message_id, interaction)
        await interaction.send_as_followup(menu2)


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

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return BindingRollView(self, label, context)

    @classmethod
    async def send_edge_menu(cls, record: type[Self], interaction: InteractionContext):
        bind_accessor = RollAccessor[BindingRoll](getter=lambda r: r.bind, setter=lambda r, v: replace(r, bind=v))
        bind_menu = GenericEdgeMenu(f"Edge Binding for {record.label}?", bind_accessor, record.message_id, interaction)
        await interaction.send_as_followup(bind_menu)

        drain_accessor = RollAccessor[BindingRoll](getter=lambda r: r.drain, setter=lambda r, v: replace(r, drain=v))
        drain_menu = GenericEdgeMenu(f"Edge Drain for {record.label}?", drain_accessor, record.message_id, interaction)
        await interaction.send_as_followup(drain_menu)


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

    @staticmethod
    def roll(
            *,
            force: int,
            summon_dice: int,
            drain_dice: int,
            limit: Optional[int] = None,
            drain_adjust: int = 0,
    ) -> SummonRoll:
        lim = limit or force

        summon = roll_hits(int(summon_dice), limit=int(lim))
        resist = roll_hits(int(force))
        drain = roll_hits(int(drain_dice))

        return SummonRoll(
            force=int(force),
            drain_adjust=int(drain_adjust),
            summon=summon,
            resist=resist,
            drain=drain,
        )

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return SummonRollView(self, label, context)

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, interaction: InteractionContext):
        summon_accessor = RollAccessor[SummonRoll](getter=lambda r: r.summon,
                                                   setter=lambda r, v: replace(r, summon=v))
        summon_menu = GenericEdgeMenu(f"Edge Summoning for {record.label}?", summon_accessor, record.message_id,
                                      interaction)
        await interaction.send_as_followup(summon_menu)

        drain_accessor = RollAccessor[SummonRoll](getter=lambda r: r.drain, setter=lambda r, v: replace(r, drain=v))
        drain_menu = GenericEdgeMenu(f"Edge Drain for {record.label}?", drain_accessor, record.message_id, interaction)
        await interaction.send_as_followup(drain_menu)


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

    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        return SpellRollView(self, label, context)

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


_magic_commands: list[tuple[str, str]] = [
    ("Cast a Spell", SpellRoll.__name__),
    ("Create Alchemical Preparation", AlchemyCreateRoll.__name__),
    ("Summon a Spirit", SummonRoll.__name__),
    ("Bind a Spirit", BindingRoll.__name__),
]

_LIMIT_MODIFIER = ArgSpec("limit_modifier", "int", aliases=("mod_limit",), suggested_values=(-1, 1, 5, 6, 7))
_LIMIT_OVERRIDE = ArgSpec("limit_override", "int", aliases=("override_limit",), suggested_values=(3, 4, 5, 6, 12))
_PRE_EDGE = ArgSpec("pre-edge", "flag", aliases=("preedge", "pre_edge"))
_SERVICES = ArgSpec("services", "int", aliases=(), suggested_values=(1, 2, 3, 4, 5))
_GREMLINS = ArgSpec("gremlins", "int", aliases=(), suggested_values=(1, 2, 3, 4))
_DRAIN_MODIFIER = ArgSpec("drain_modifier", "int", aliases=tuple("dv_mod"), suggested_values=(-3, -1, 0, 3))

BINDING_REQUIRED = _SERVICES
BINDING_OPTIONAL = _LIMIT_OVERRIDE, _LIMIT_MODIFIER, _DRAIN_MODIFIER
SPELL_REQUIRED = _DRAIN_MODIFIER
SPELL_OPTIONAL = _LIMIT_OVERRIDE, _LIMIT_MODIFIER

ALL_MAGIC_EXTRA_SPECS = _LIMIT_OVERRIDE, _LIMIT_MODIFIER, _DRAIN_MODIFIER

drain_modifier = "Drain value modifier. For conjury, this will usually be 0 unless you are spending radical reagents.",


async def handle_magic_autocomplete(interaction: Interaction[ClientContext], current: str) -> list[str]:
    action_name = getattr(interaction.namespace, "action", None)

    match action_name:
        case BindingRoll.__name__:
            extra_specs = BINDING_REQUIRED + BINDING_OPTIONAL
        case _:
            extra_specs = ALL_MAGIC_EXTRA_SPECS

    suggestions = build_args_autocomplete_suggestions(
        current,
        extra_specs,
        maximum_suggestions=25,
    )
    return [app_commands.Choice(name=text or "(empty)", value=text) for text in suggestions]


def parse_extras_list(extras: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}

    for item in extras:
        key, sep, value = item.partition("=")
        key = key.strip()
        if not key:
            continue

        result[key] = value.strip() if sep else ""

    return result


def parse_int(s: str | None, default: int | None = None) -> int | None:
    try:
        return int(s) if s is not None else default
    except ValueError:
        return default


def register(group: app_commands.Group) -> None:
    @group.command(name="magic", description="All magic-related rolls (SR5).")
    @app_commands.describe(
        action="What type of magical action you are initiating",
        label="A label to describe the roll.",
        force="Force of the effect",
        action_dice="Dice pool (1-99).",
        drain_dice="Drain resistance dice pool (1-99).",
        extras="Additional action-specific data. Autocompletes."
    )
    @app_commands.choices(action=[
        app_commands.Choice(
            name=k,
            value=v
        ) for (k, v) in _magic_commands
    ])
    @app_commands.autocomplete(extras=handle_magic_autocomplete)
    async def cmd(
            interaction: Interaction[ClientContext],
            action: app_commands.Choice[str],
            label: str,
            force: app_commands.Range[int, 1, 50],
            action_dice: app_commands.Range[int, 1, 99],
            drain_modifier: app_commands.Range[int, -99, 99],
            drain_dice: app_commands.Range[int, 1, 99],
            extras: str
    ) -> None:
        extra_args = dict(parse_extras_list(extras.split(",")))
        limit = parse_int(extra_args.get("limit"), None)
        match action.value:
            case SpellRoll.__name__:
                result = SpellRoll.roll(
                    force=int(force),
                    cast_dice=int(action_dice),
                    drain_value=int(force + drain_modifier),
                    drain_dice=int(drain_dice),
                    limit=int(limit) if limit is not None else None,
                )
            case AlchemyCreateRoll.__name__:
                result = AlchemyCreateRoll.roll(
                    force=int(force),
                    cast_dice=int(action_dice),
                    drain_value=int(force + drain_modifier),
                    drain_dice=int(drain_dice),
                    limit=int(limit) if limit is not None else None,
                )
            case SummonRoll.__name__:
                result = SummonRoll.roll(
                    force=int(force),
                    summon_dice=int(action_dice),
                    drain_dice=int(drain_dice),
                    limit=limit or 0,
                    drain_adjust=int(drain_modifier),
                )
            case BindingRoll.__name__:
                result = BindingRoll.roll(
                    force=int(force),
                    services_in=int(extra_args.get("services")),
                    bind_dice=int(action_dice),
                    drain_dice=int(drain_dice),
                    drain_adjust=int(drain_modifier),
                    limit=int(limit) if limit is not None else None,
                )
        await InteractionContext(interaction).transmit_result(label=label, result=result)
