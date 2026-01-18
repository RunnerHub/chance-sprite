from __future__ import annotations

import logging
from typing import Any, override

from discord import ButtonStyle, Interaction, InteractionMessage, ui

from chance_sprite.message_cache.roll_record_base import ResistableRoll
from chance_sprite.rollui.base_roll_view import BaseView
from chance_sprite.rollui.modals import InPlaceResistModal
from chance_sprite.sprite_context import InteractionContext

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
    async def callback(self, interaction: Interaction) -> Any:
        context = InteractionContext(interaction)
        # give the interaction a response so that our arbitrary number of menu followups will go through
        await interaction.response.defer(ephemeral=True)
        msg = interaction.message
        if msg is None:
            await interaction.followup.send(
                "Couldn't access the clicked message.", ephemeral=True
            )
            return

        message_record = context.client.message_store[msg.id]
        if message_record is None:
            await interaction.followup.send(
                "Couldn't find that roll in the bot's database. Could be a bug, or maybe it expired?",
                ephemeral=True,
            )
            return

        roll_result = message_record.roll_result
        user = interaction.user
        if isinstance(roll_result, ResistableRoll):
            owners = roll_result.current_owners(message_record, context)
        else:
            owners = [message_record.owner_id]

        if user.id not in owners:
            await interaction.followup.send(
                "You are not a participant in that roll.", ephemeral=True
            )
            return
        interaction_message = await interaction.original_response()
        context.cache_message_handle(interaction_message)

        await message_record.roll_result.send_menu(message_record, context)


class ResistButton(ui.Button):
    def __init__(self):
        super().__init__(label="Resist")
        self.original_post: InteractionMessage | None = None
        self.custom_id = "resist_menu"
        self.style = ButtonStyle.primary

    @override
    async def callback(self, interaction: Interaction):
        context = InteractionContext(interaction)
        msg = interaction.message
        if msg is None:
            await interaction.response.send_message(
                "Couldn't access the clicked message.", ephemeral=True
            )
            return

        message_record = context.client.message_store[msg.id]
        if message_record is None:
            await interaction.response.send_message(
                "Couldn't find that roll in the bot's database. Could be a bug, or maybe it expired?",
                ephemeral=True,
            )
            return

        roll_result = message_record.roll_result
        if isinstance(roll_result, ResistableRoll):
            user = interaction.user
            already_resisted = roll_result.already_resisted()
            if user.id in already_resisted:
                await interaction.response.send_message(
                    "You already resisted that roll! Hit 'Menu' to edge or adjust if applicable.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_modal(InPlaceResistModal(message_record))
            interaction_message = await interaction.original_response()
            context.cache_message_handle(interaction_message)
