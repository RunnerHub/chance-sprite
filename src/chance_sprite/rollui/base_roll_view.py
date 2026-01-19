from __future__ import annotations

import re

from discord import File, UnfurledMediaItem, ui

from chance_sprite.sprite_context import InteractionContext


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
        if not isinstance(self.container.children[-1], ui.Separator):
            self.add_separator()
        button_row = ui.ActionRow(*buttons)
        self.container.add_item(button_row)
