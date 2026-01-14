from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta

from discord import (
    DMChannel,
    Interaction,
    InteractionCallbackResponse,
    InteractionMessage,
)
from discord.ext import commands

from chance_sprite.emojis.emoji_manager import EmojiManager
from chance_sprite.file_sprite import MessageRecordStore
from chance_sprite.message_cache.message_record import MessageRecord
from chance_sprite.message_cache.roll_record_base import RollRecordBase
from chance_sprite.rollui.base_roll_view import BaseMenuView
from chance_sprite.sprite_utils import has_get_partial_message

log = logging.getLogger(__name__)


class ClientContext(commands.Bot):
    def __init__(
        self,
        *,
        emoji_manager: EmojiManager,
        lite_emojis: EmojiManager,
        message_cache: MessageRecordStore,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.emoji_manager = emoji_manager
        self.lite_emojis = lite_emojis
        self.message_store: MessageRecordStore = message_cache
        self.message_handles: dict[int, InteractionMessage] = dict()
        self.base_command_name = None


class InteractionContext:
    def __init__(self, interaction: Interaction):
        assert isinstance(interaction.client, ClientContext)
        self.interaction = interaction
        self.emoji_manager = interaction.client.emoji_manager
        self.lite_emojis = interaction.client.lite_emojis
        self.message_store = interaction.client.message_store
        self.message_handles = interaction.client.message_handles

    def get_cached_record(self, message_id: int):
        return self.message_store[message_id]

    def cache_message_handle(self, handle: InteractionMessage):
        self.message_handles[handle.id] = handle

    def get_cached_message_handle(self, id: int):
        return self.message_handles.get(id)

    async def update_original(
        self, old_record: MessageRecord, new_result: RollRecordBase
    ):
        await self.defer_if_needed()
        view = new_result.build_view(old_record.label, self)
        if view.content_length() > 4000:
            self.emoji_manager = self.lite_emojis
            view = new_result.build_view(old_record.label, self)
        # emojis = interaction.client.emoji_manager.packs
        # TODO: await emoji sync and update
        # if not context.emoji_manager.loaded:
        #     pass
        try:
            cached_message_handle = self.get_cached_message_handle(
                old_record.message_id
            )
            if cached_message_handle:
                await cached_message_handle.edit(view=view)
                new_record = replace(old_record, roll_result=new_result)
                self.message_store.put(new_record)
                log.info("Edited via cached message")
                return new_record
            else:
                log.info("Message key not cached: %d", old_record.message_id)
        except Exception as e:
            log.info("Error editing cached message: %s", e)
        try:
            if not has_get_partial_message(self.interaction.channel):
                log.info(
                    "Interaction channel is not partial-messageable: %r",
                    type(self.interaction.channel),
                )
                return None
            original_message = self.interaction.channel.get_partial_message(
                old_record.message_id
            )
            # Edit the original message
            await original_message.edit(view=view)
            new_record = replace(old_record, roll_result=new_result)
            self.message_store.put(new_record)
            log.info("Edited via partial message")
            return new_record
        except Exception as e:
            log.info("Failed to edit interaction via partial message: %s", e)

    async def transmit_result(self, label: str, result: RollRecordBase):
        interaction = self.interaction
        # TODO: await emoji sync and update
        primary_view = result.build_view(label, self)
        if primary_view.content_length() > 4000:
            self.emoji_manager = self.lite_emojis
            primary_view = result.build_view(label, self)
        send_message_response: InteractionCallbackResponse = (
            await interaction.response.send_message(
                view=primary_view,
            )
        )
        message_id = send_message_response.message_id
        if isinstance(send_message_response.resource, InteractionMessage):
            message: InteractionMessage = send_message_response.resource
            self.cache_message_handle(message)
        now = datetime.now()
        expires_at = now + timedelta(days=7)
        try:
            if isinstance(interaction.channel, DMChannel):
                log.info(
                    f"User [{interaction.user.display_name}] rolled [{result.__class__.__name__}] in [{[user.display_name for user in interaction.channel.recipients]}]"
                )
            elif interaction.channel:
                log.info(
                    f"User [{interaction.user.display_name}] rolled [{result.__class__.__name__}] in [{interaction.channel.name}]"
                )
            else:
                log.info(
                    f"User [{interaction.user.display_name}] rolled [{result.__class__.__name__}] in [??? NoneChannel ???]"
                )
        except Exception as e:
            log.info(f"Unusual event when logging interaction: {e}")
            log.info(f"Interaction details: {interaction}")

        if message_id:
            record = MessageRecord(
                message_id=message_id,
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id or 0,
                owner_id=interaction.user.id,
                label=label,
                created_at=int(now.timestamp()),
                expires_at=int(expires_at.timestamp()),
                roll_result=result,
            )
            self.message_store.put(record)
            return record

    async def defer_if_needed(self):
        # noinspection PyUnresolvedReferences
        if not self.interaction.response.is_done():
            try:
                await self.interaction.response.defer()
            except Exception as e:
                log.info("Exception in deferral: %s", e)

    async def transmit_result_from_interaction(self):
        if not self.interaction.message:
            log.error(
                f"Couldn't find message on transmitted interaction: {self.interaction}"
            )
        else:
            message_id = self.interaction.message.id
            message_record = self.message_store[message_id]
            label = message_record.label
            result = message_record.roll_result
            await self.transmit_result(label, result)
        await self.defer_if_needed()

    async def send_as_followup(self, menu: BaseMenuView):
        followup_message = await self.interaction.followup.send(
            view=menu, wait=True, ephemeral=True
        )
        menu.followup_message = followup_message
        # self.followup_message = await interaction.edit_original_response(view=self)
