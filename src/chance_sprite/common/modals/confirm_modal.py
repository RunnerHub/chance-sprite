from __future__ import annotations

import discord
from discord import ui


class ConfirmModal(ui.Modal):
    def __init__(self, title: str, *, body: str, do_action, on_after):
        super().__init__(title=title, timeout=None)
        self._do_action = do_action      # async (interaction) -> None
        self._on_after = on_after        # async (interaction) -> None
        confirm = ui.TextDisplay(body)
        self.add_item(confirm)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._do_action(interaction)
        await self._on_after(interaction)
