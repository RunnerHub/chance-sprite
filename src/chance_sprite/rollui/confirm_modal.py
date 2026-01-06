from __future__ import annotations

from discord import ui, Interaction

from chance_sprite.sprite_context import ClientContext


class ConfirmModal(ui.Modal):
    def __init__(self, title: str, *, body: str, do_action, on_after):
        super().__init__(title=title, timeout=None)
        self._do_action = do_action  # async (context) -> None
        self._on_after = on_after  # async (context) -> None
        confirm: ui.TextDisplay = ui.TextDisplay(body)
        self.add_item(confirm)

    async def on_submit(self, context: Interaction[ClientContext]) -> None:
        await self._do_action(context)
        await self._on_after(context)
