from __future__ import annotations

import re
from dataclasses import replace
from typing import Callable

from discord import ButtonStyle, File, Interaction, UnfurledMediaItem, ui

from chance_sprite.message_cache.roll_record_base import RollRecordBase
from chance_sprite.result_types.hits_result import HitsResult
from chance_sprite.roller import close_call, push_the_limit, second_chance
from chance_sprite.rollui.modal_inputs import LabeledNumberField, ValidLabel
from chance_sprite.rollui.roll_accessor import DirectRollAccessor
from chance_sprite.sprite_context import InteractionContext
from chance_sprite.sprite_utils import Glitch


class BaseView(ui.LayoutView):
    def __init__(self, *, timeout: float | None = None):
        super().__init__(timeout=timeout)


CROSSOUT_SUB = re.compile(r"~~~~")


class BaseRollView(BaseView):
    def __init__(
        self,
        label: str,
        accent_color: int,
        context: InteractionContext,
    ) -> None:
        super().__init__(timeout=None)

        roll_record = context.get_roll_record()
        owner_id = roll_record.owner_id if roll_record else 0
        (username, avatar) = context.get_avatar(owner_id)

        if not label.strip():
            label = "(no label)"
        header_txt = ui.TextDisplay(f"### {username}\n{label.strip()}")
        header_section = ui.Section(
            header_txt,
            accessory=ui.Thumbnail(avatar),
        )
        self.container = ui.Container(
            header_section, ui.Separator(), accent_color=accent_color
        )
        self.add_item(self.container)

    def add_text(self, txt: str):
        self.container.add_item(ui.TextDisplay(CROSSOUT_SUB.sub("", txt)))

    def add_long_text(self, blocks: list[str]):
        # Split into chunks
        chunk = ""
        for block in blocks:
            chunk = (chunk + "\n" + block).strip() if chunk else block.strip()

        if chunk:
            self.add_text(chunk)

    def add_separator(self):
        self.container.add_item(ui.Separator())

    def add_section(self, txt: str, icon: str | File | UnfurledMediaItem):
        section = ui.Section(
            ui.TextDisplay(txt),
            accessory=ui.Thumbnail(icon),
        )
        self.container.add_item(section)

    def add_buttons(self, *buttons: ui.Button):
        self.add_separator()
        button_row = ui.ActionRow(*buttons)
        self.container.add_item(button_row)


class BaseMenuView[R: RollRecordBase](BaseView):
    def __init__(self, record_id: int):
        super().__init__(timeout=None)
        self.container = ui.Container(accent_color=0x44CC88)
        self.add_item(self.container)
        self.last_action_row: ui.ActionRow | None = None
        self.record_id = record_id

    def add_action_row(self):
        self.last_action_row = ui.ActionRow()
        self.container.add_item(self.last_action_row)
        return self.last_action_row

    def add_button(self, button: ui.Button):
        if self.last_action_row and len(self.last_action_row.children) < 5:
            self.last_action_row.add_item(button)
        else:
            self.add_action_row().add_item(button)

    def add_text(self, txt: str):
        self.container.add_item(ui.TextDisplay(txt))
        self.last_action_row = None

    def create_button(
        self,
        label: str,
        *,
        style=ButtonStyle.primary,
        emoji=None,
        custom_id=None,
        callback,
    ):
        button = ui.Button(
            style=style, label=label, disabled=False, emoji=emoji, custom_id=custom_id
        )
        button.callback = callback
        self.add_button(button)
        return button

    def modal_button(
        self,
        label: str,
        *,
        title: str | None = None,
        body: str | None = None,
        fields: list[ValidLabel] | None = None,
        style: ButtonStyle = ButtonStyle.primary,
    ):
        from chance_sprite.rollui.modals import BuiltModal

        def _decorator(transform: Callable[..., RollRecordBase]) -> ui.Button:
            button = ui.Button(label=label, style=style)
            self.add_button(button)

            async def _cb(interaction: Interaction):
                modal = BuiltModal(
                    title=title or label,
                    body=body,
                    fields=list(fields or []),
                    view=self,
                    transform=transform,
                )
                await interaction.response.send_modal(modal)

            button.callback = _cb
            return button

        return _decorator

    async def apply_transform(
        self,
        interaction: Interaction,
        transform: Callable[..., RollRecordBase],
        *args,
    ) -> None:
        context = InteractionContext(interaction)
        record = context.get_cached_record(self.record_id)

        # TODO: reassess ownership gating
        if interaction.user.id not in record.current_owners(context):
            return

        new_record = transform(record.roll_result, *args)

        await context.update_original(record, new_record)

        await context.update_menu(self)

    def add_edge_buttons(self, record: R, accessor: DirectRollAccessor[R]):
        initial_result = accessor.get(record)
        edge_buttons = list[ui.Button]()

        def disable(button: ui.Button):
            button.disabled = True
            button.style = ButtonStyle.secondary

        def disable_all():
            [disable(button) for button in edge_buttons]

        @self.modal_button(
            "♻️",
            title="2nd Chance",
            body="Use Edge to reroll failures?",
            fields=[],
        )
        def second_chance_button(roll: R):
            disable_all()
            return accessor.update(roll, second_chance(accessor.get(roll)))

        edge_buttons.append(second_chance_button)

        @self.modal_button(
            "⚡",
            title="Push Limit",
            body="Enter your edge score to break the limit with exploding dice.",
            fields=[LabeledNumberField("Edge", 0, 12)],
        )
        def push_limit_button(roll: R, dice: int):
            disable_all()
            return accessor.update(roll, push_the_limit(accessor.get(roll), dice))

        edge_buttons.append(push_limit_button)

        @self.modal_button(
            "🛡️",
            title="Close Call",
            body="Use Edge to mitigate a glitch?",
            fields=[],
        )
        def close_call_button(roll: R):
            disable_all()
            return accessor.update(roll, close_call(accessor.get(roll)))

        edge_buttons.append(close_call_button)

        # Already edged
        if type(initial_result) is not HitsResult:
            disable_all()

        # Already at limit
        if 0 < initial_result.limit <= initial_result.dice_hits:
            disable(second_chance_button)

        # No glitch to negate
        if initial_result.glitch == Glitch.NONE:
            disable(close_call_button)

        return edge_buttons

    def add_adjust_dice_button(self, record: R, accessor: DirectRollAccessor[R]):
        @self.modal_button(
            "±🎲",
            title="Adjust Dice",
            body="Adjust dice pool ±. Rolls are kept.",
            fields=[LabeledNumberField("Dice", -50, 50)],
        )
        def adjust_dice_button(roll: R, dice: int) -> R:
            return accessor.update(roll, accessor.get(roll).adjust_dice(dice))

    def add_adjust_limit_button(self, record: R, accessor: DirectRollAccessor[R]):
        @self.modal_button(
            "±🚧",
            title="Adjust Limit",
            body="Enter the new limit.",
            fields=[LabeledNumberField("Limit", 0, 99)],
        )
        def adjust_limit_button(roll: R, limit: int) -> R:
            return accessor.update(roll, replace(accessor.get(roll), limit=limit))

    def add_standard_buttons(self, record: R, accessor: DirectRollAccessor[R]):
        self.add_edge_buttons(record, accessor)
        self.add_adjust_dice_button(record, accessor)
        self.add_adjust_limit_button(record, accessor)
