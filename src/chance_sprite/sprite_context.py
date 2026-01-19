from __future__ import annotations

import logging
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from discord import (
    DMChannel,
    Interaction,
    InteractionCallbackResponse,
    InteractionMessage,
)

from chance_sprite.message_cache.message_record import MessageRecord
from chance_sprite.message_cache.roll_record_base import RollRecordBase
from chance_sprite.message_cache.webhook_handle import WebhookHandle

if TYPE_CHECKING:
    from chance_sprite.rollui.base_roll_view import BaseMenuView

from chance_sprite.sprite_utils import epoch_seconds, has_get_partial_message

log = logging.getLogger(__name__)


class InteractionContext:
    def __init__(self, interaction: Interaction):
        self.interaction = interaction
        from .discord_sprite import DiscordSprite

        assert isinstance(interaction.client, DiscordSprite)
        self.client = interaction.client
        self.emoji_manager = interaction.client.emoji_manager
        self.lite_emojis = interaction.client.lite_emojis

        self.client.user_avatar_store.update_avatar(
            self.interaction.user.id,
            self.interaction.guild_id or 0,
            self.interaction.user.display_name,
            str(self.interaction.user.display_avatar),
        )

    def get_roll_record(self):
        record = None
        if not self.interaction.message:
            return None

        message_id = self.interaction.message.id
        record = self.client.message_store.get(message_id)
        if record:
            return record

        menu: WebhookHandle | None = self.client.webhook_handles.get(message_id)
        if not menu:
            return None

        original_id = menu.original_target
        if not original_id:
            return None

        return self.get_cached_record(original_id)

    def get_cached_record(self, message_id: int):
        return self.client.message_store[message_id]

    def cache_message_handle(self, handle: InteractionMessage):
        self.client.message_handles[handle.id] = handle

    def get_cached_message_handle(self, id: int):
        return self.client.message_handles.get(id)

    def get_avatar(self, user_id: int | None = None):
        lookup_id = user_id if user_id else self.interaction.user.id
        guild_id = self.interaction.guild_id or 0
        return self.client.user_avatar_store.get_avatar(lookup_id, guild_id)

    async def update_original(
        self, old_record: MessageRecord, new_result: RollRecordBase
    ):
        await self.defer_if_needed()
        view = new_result.build_view(old_record.label, self)
        if view.content_length() > 4000:
            self.emoji_manager = self.client.lite_emojis
            view = new_result.build_view(old_record.label, self)
        try:
            cached_message_handle = self.get_cached_message_handle(
                old_record.message_id
            )
            if cached_message_handle:
                await cached_message_handle.edit(view=view)
                new_record = replace(old_record, roll_result=new_result)
                self.client.message_store.put(new_record)
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
            await original_message.edit(view=view)
            new_record = replace(old_record, roll_result=new_result)
            self.client.message_store.put(new_record)
            log.info("Edited via partial message")
            return new_record
        except Exception as e:
            log.info("Failed to edit interaction via partial message: %s", e)

    async def update_menu(self, view: "BaseMenuView"):
        if self.interaction.message:
            await self.interaction.followup.edit_message(
                self.interaction.message.id, view=view
            )
        else:
            log.error("couldn't edit interaction message")

    async def transmit_result(self, label: str, result: RollRecordBase):
        interaction = self.interaction
        primary_view = result.build_view(label, self)
        if primary_view.content_length() > 4000:
            self.emoji_manager = self.client.lite_emojis
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
            self.client.message_store.put(record)
            return record

    async def defer_if_needed(self):
        # noinspection PyUnresolvedReferences
        if not self.interaction.response.is_done():
            try:
                await self.interaction.response.defer()
            except Exception as e:
                frame = sys._getframe(1)

                log.info(
                    "Exception in deferral (%s:%d in %s): %s",
                    frame.f_code.co_filename,
                    frame.f_lineno,
                    frame.f_code.co_name,
                    e,
                )

    async def send_as_followup(self, menu: "BaseMenuView"):
        original_message_id = (
            self.interaction.message.id if self.interaction.message else None
        )
        followup_message = await self.interaction.followup.send(
            view=menu, wait=True, ephemeral=True
        )
        webhook_id = self.interaction.followup.id
        message_id = followup_message.id
        expires_at = epoch_seconds() + 890  # 15 mins - 10 seconds
        handle = WebhookHandle(
            message_id,
            webhook_id,
            expires_at,
            original_target=original_message_id,
        )
        self.client.webhook_handles.set(message_id, handle, expires_at=expires_at)
