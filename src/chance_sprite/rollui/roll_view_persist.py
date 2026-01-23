from __future__ import annotations

import logging
from typing import Any, override

from discord import ButtonStyle, Interaction, InteractionMessage, ui

from chance_sprite.message_cache.roll_record_base import ResistableRoll
from chance_sprite.rollui.base_roll_view import BaseView
from chance_sprite.rollui.modal_inputs import LabeledBooleanField, LabeledNumberField
from chance_sprite.rollui.modals import BuiltModal
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

            def transform(
                roll: ResistableRoll,
                context: InteractionContext,
                dice: int,
                limit: int,
                pre_edge: bool,
            ):
                record = context.get_cached_record(msg.id)
                if len(record.roll_result.already_resisted()) < 10:
                    return roll.resist(context, dice, limit=limit, pre_edge=pre_edge)
                else:
                    raise ValueError("Too many resistors!")

            async def on_fail(
                roll: ResistableRoll,
                context: InteractionContext,
                dice: int,
                limit: int,
                pre_edge: bool,
            ):
                from chance_sprite.roll_types.basic import roll_simple

                record = context.get_cached_record(msg.id)
                threshold = roll.resistance_target()
                threshold_roll = roll_simple(
                    dice=dice, threshold=threshold, limit=limit, pre_edge=pre_edge
                )
                await context.transmit_result(
                    f"Resisting {record.label} ({threshold})", threshold_roll
                )

            modal = BuiltModal(
                title="Resistance roll",
                body=f"Rolling to resist {message_record.label} ({roll_result.resistance_target()} hits)",
                fields=[
                    LabeledNumberField("Number of Dice", 0, 99),
                    LabeledNumberField("Limit (if applicable)", 0, 99, required=False),
                    LabeledBooleanField(
                        "Pre-edge? (add your edge above, if so)",
                        default=False,
                    ),
                ],
                menu_view=None,
                original_view_id=msg.id,
                transform=transform,
                on_fail=on_fail,
            )
            await interaction.response.send_modal(modal)
            interaction_message = await interaction.original_response()
            context.cache_message_handle(interaction_message)
