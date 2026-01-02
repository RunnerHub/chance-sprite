from __future__ import annotations

import discord
from discord import ui


class DiceInputModal(ui.Modal):
    def __init__(self, title: str, body: str, *, do_action, on_after, min_val:int=0, max_val:int=99):
        super().__init__(title=title, timeout=None)
        self._do_action = do_action      # async (interaction, extra_dice:int) -> None
        self._on_after = on_after        # async (interaction) -> None
        self.dice_to_add = ui.TextInput(
            label=body,
            placeholder="e.g. 3",
            required=True,
            min_length=1,
            max_length=3,
        )
        self.min_val = min_val
        self.max_val = max_val
        self.add_item(self.dice_to_add)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.dice_to_add.value).strip()
        try:
            extra = int(raw)
        except ValueError:
            await interaction.response.send_message("That isn’t a number.", ephemeral=True)
            return

        if extra < self.min_val or extra > self.max_val:
            await interaction.response.send_message(f"Pick a dice count between {min} and {max}.", ephemeral=True)
            return

        await self._do_action(interaction, extra)
        await self._on_after(interaction)
