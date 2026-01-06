from __future__ import annotations

import logging
from typing import override, Any

import discord
from discord import ui, ButtonStyle, Interaction

from chance_sprite.sprite_context import ClientContext, InteractionContext

log = logging.getLogger(__name__)


class EdgeMenuPersist(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(EdgeMenuButton())


class EdgeMenuButton(ui.Button):
    def __init__(self):
        super().__init__()
        self.label = "Menu"
        self.custom_id = "edge_menu"
        self.style = ButtonStyle.secondary

    @override
    async def callback(self, interaction: Interaction[ClientContext]) -> Any:
        interaction_context = InteractionContext(interaction)
        # give the interaction a response so that our arbitrary number of menu followups will go through
        await interaction.response.defer(ephemeral=True)
        msg = interaction.message
        if msg is None:
            await interaction.followup.send("Couldn't access the clicked message.", ephemeral=True)
            return

        message_record = interaction.client.message_cache[msg.id]
        if message_record is None:
            await interaction.followup.send(
                "Couldn't find that roll in the bot's database. Could be a bug, or maybe it expired?", ephemeral=True)
            return

        user = interaction.user
        if user.id != message_record.owner_id:
            await interaction.followup.send("You are not the initiator of that message.", ephemeral=True)
            return
        interaction_message = await interaction.original_response()
        interaction_context.cache_message_handle(interaction_message)

        await message_record.roll_result.send_edge_menu(message_record, interaction_context)
