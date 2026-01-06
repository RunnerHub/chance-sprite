from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta

from discord import ui, Interaction, InteractionCallbackResponse, InteractionMessage
from discord.ext import commands
from discord.ui.view import LayoutView

from chance_sprite.emojis.emoji_manager import EmojiManager
from chance_sprite.file_sprite import RollRecordCacheFile
from chance_sprite.message_cache.message_record import MessageRecord
from chance_sprite.message_cache.roll_record_base import RollRecordBase

log = logging.getLogger(__name__)


class ClientContext(commands.Bot):
    emoji_manager: EmojiManager
    message_cache: RollRecordCacheFile
    message_handles: dict[int, InteractionMessage]

    def __init__(self, *, emoji_manager: EmojiManager, message_cache: RollRecordCacheFile, **kwargs):
        super().__init__(**kwargs)
        self.emoji_manager = emoji_manager
        self.message_cache = message_cache
        self.message_handles = dict()


class InteractionContext:
    def __init__(self, interaction: Interaction[ClientContext]):
        self.interaction = interaction

    def get_cached_record(self, id: int):
        return self.interaction.client.message_cache[id]

    def cache_message_handle(self, handle: InteractionMessage):
        self.interaction.client.message_handles[handle.id] = handle

    async def update_original(self, old_record: MessageRecord, new_result: RollRecordBase):
        await self.defer_if_needed()
        interaction = self.interaction
        view_builder = new_result.build_view(old_record.label)
        context = interaction.client
        emojis = interaction.client.emoji_manager.packs
        if not emojis:
            # TODO: don't choke
            return
        view = view_builder(context)
        try:
            cached_message_handle = context.message_handles[old_record.message_id]
            await cached_message_handle.edit(view=view)
            new_record = replace(old_record, roll_result=new_result)
            context.message_cache.put(new_record)
            log.info("Edited via cached message")
            return new_record
        except Exception as e:
            log.info("Message key not cached: %s", e)
        try:
            original_message = interaction.channel.get_partial_message(old_record.message_id)
            # Edit the original message
            await original_message.edit(view=view)
            new_record = replace(old_record, roll_result=new_result)
            context.message_cache.put(new_record)
            log.info("Edited via partial message")
            return new_record
        except Exception as e:
            log.info("Failed to edit interaction via partial message: %s", e)

    async def transmit_result(self, label: str, result: RollRecordBase):
        interaction = self.interaction
        context = self.interaction.client
        # TODO: await emoji sync and update
        if context.emoji_manager.loaded:
            view_builder = result.build_view(label)
            primary_view = view_builder(context)
        else:
            primary_view = ui.LayoutView()
            primary_view.add_item(ui.TextDisplay("Still loading emojis, please wait!"))
        send_message_response: InteractionCallbackResponse[ClientContext] = await interaction.response.send_message(
            view=primary_view)
        message_id = send_message_response.message_id
        if isinstance(send_message_response.resource, InteractionMessage):
            message: InteractionMessage = send_message_response.resource
            context.message_handles[message.id] = message
        now = datetime.now()
        expires_at = now + timedelta(days=7)
        try:
            log.info(
                f"User [{interaction.user.display_name}] rolled [{result.__class__.__name__}] in [{interaction.channel.name}]")
        except Exception as e:
            log.info(f"Unusual event when logging interaction: {e}")
            log.info(f"Interaction details: {interaction}")
        record = MessageRecord(
            message_id=message_id,
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id or 0,
            owner_id=interaction.user.id,
            label=label,
            created_at=int(now.timestamp()),
            expires_at=int(expires_at.timestamp()),
            roll_result=result
        )
        context.message_cache.put(record)
        return record

    async def defer_if_needed(self):
        if not self.interaction.response.is_done():
            try:
                await self.interaction.response.defer()
            except Exception as e:
                log.info("Exception in deferral: %s", e)

    async def transmit_result_from_interaction(self):
        interaction = self.interaction
        context = interaction.client
        if not interaction.message:
            log.error(f"Couldn't find message on transmitted interaction: {interaction}")
        else:
            message_id = interaction.message.id
            message_record = context.message_cache[message_id]
            label = message_record.label
            result = message_record.roll_result
            await self.transmit_result(label, result)
        await self.defer_if_needed()

    async def send_as_followup(self, menu: LayoutView):
        followup_message = await self.interaction.followup.send(view=menu, wait=True, ephemeral=True)
        menu.followup_message = followup_message
        # self.followup_message = await interaction.edit_original_response(view=self)
