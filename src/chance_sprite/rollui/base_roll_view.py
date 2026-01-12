from __future__ import annotations
from typing import TYPE_CHECKING


from discord import MediaGalleryItem, WebhookMessage, ui

if TYPE_CHECKING:
    from chance_sprite.sprite_context import InteractionContext

class BaseView(ui.LayoutView):
    def __init__(self, *, timeout: float | None = None):
        super().__init__(timeout=timeout)

class BaseRollView(BaseView):
    def __init__(self, label: str, accent_color: int, context: InteractionContext) -> None:
        super().__init__(timeout=None)
        if not label.strip():
            label = "(no label)"
        header_txt = ui.TextDisplay(
            f"### {context.interaction.user.display_name}\n"
            f"{label.strip()}"
        )
        header_section = ui.Section(header_txt, accessory= ui.Thumbnail(context.interaction.user.display_avatar.url))
        self.container = ui.Container(header_section, ui.Separator(), accent_color = accent_color)
        self.add_item(self.container)
    
    def add_text(self, txt: str):
        self.container.add_item(ui.TextDisplay(txt))

    def add_long_text(self, blocks: list[str]):
        # Split into chunks
        chunk = ""
        for block in blocks:
            candidate = (chunk + "\n" + block).strip() if chunk else block
            if len(candidate) > 1800:  # keep headroom
                self.add_text(chunk)
                chunk = block
            else:
                chunk = candidate

        if chunk:
            self.add_text(chunk)

    def add_separator(self):
        self.container.add_item(ui.Separator())

    def add_buttons(self, *buttons: ui.Button):
        self.add_separator()
        button_row = ui.ActionRow(*buttons)
        self.container.add_item(button_row)




class BaseMenuView(BaseView):
    def __init__(self):
        super().__init__(timeout=None)
        self.followup_message: WebhookMessage | None = None