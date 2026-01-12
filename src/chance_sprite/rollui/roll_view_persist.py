from __future__ import annotations

import logging
from typing import override, Any

from discord import ui, ButtonStyle, Interaction, InteractionMessage

from chance_sprite.rollui.base_roll_view import BaseView
from chance_sprite.rollui.modals import ResistModal
from chance_sprite.sprite_context import ClientContext, InteractionContext


log = logging.getLogger(__name__)


class RollViewPersist(BaseView):
    def __init__(self):
        super().__init__()
        self.add_item(EdgeMenuButton())
        self.add_item(ResistButton())


class EdgeMenuButton(ui.Button):
    def __init__(self):
        super().__init__()
        self.label = "Menu"
        self.custom_id = "edge_menu"
        self.style = ButtonStyle.secondary

    @override
    async def callback(self, interaction: Interaction[ClientContext]) -> Any:
        context = InteractionContext(interaction)
        # give the interaction a response so that our arbitrary number of menu followups will go through
        await interaction.response.defer(ephemeral=True)
        msg = interaction.message
        if msg is None:
            await interaction.followup.send(
                "Couldn't access the clicked message.", ephemeral=True
            )
            return

        message_record = interaction.client.message_store[msg.id]
        if message_record is None:
            await interaction.followup.send(
                "Couldn't find that roll in the bot's database. Could be a bug, or maybe it expired?",
                ephemeral=True,
            )
            return

        user = interaction.user
        if user.id != message_record.owner_id:
            await interaction.followup.send(
                "You are not the initiator of that message.", ephemeral=True
            )
            return
        interaction_message = await interaction.original_response()
        context.cache_message_handle(interaction_message)

        await message_record.roll_result.send_edge_menu(message_record, context)


class ResistButton(ui.Button):
    def __init__(self):
        super().__init__(label="Resist")
        self.original_post: InteractionMessage | None = None
        self.custom_id = "resist_menu"
        self.style = ButtonStyle.primary

    @override
    async def callback(self, interaction: Interaction[ClientContext]):
        context = InteractionContext(interaction)
        msg = interaction.message
        if msg is None:
            await interaction.followup.send(
                "Couldn't access the clicked message.", ephemeral=True
            )
            return

        message_record = interaction.client.message_store[msg.id]
        if message_record is None:
            await interaction.followup.send(
                "Couldn't find that roll in the bot's database. Could be a bug, or maybe it expired?",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ResistModal(message_record))
        interaction_message = await interaction.original_response()
        context.cache_message_handle(interaction_message)
