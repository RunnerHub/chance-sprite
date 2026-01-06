from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta

import discord
from discord import ui, Interaction
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

    def __init__(self, *, emoji_manager: EmojiManager, message_cache: RollRecordCacheFile, **kwargs):
        super().__init__(**kwargs)
        self.emoji_manager = emoji_manager
        self.message_cache = message_cache


class InteractionContext:
    def __init__(self, interaction: Interaction[ClientContext]):
        self.interaction = interaction

    async def update_message(self, old_record: MessageRecord, new_result: RollRecordBase):
        interaction = self.interaction
        log.info(f"Updating message in Channel {interaction.channel_id}: {interaction.channel}")
        view_builder = new_result.build_view(old_record.label)
        context = interaction.client
        emojis = interaction.client.emoji_manager.packs
        if not emojis:
            return
        view = view_builder(context)
        # # Doesn't seem to ever work
        # try:
        #     await interaction.message.edit(view=view)
        #     await interaction.defer()
        # except discord.DiscordException:
        #     log.info("Failed to edit interaction via interaction message object")
        try:
            channel = interaction.channel
            if hasattr(channel, "get_partial_message"):
                original_message = channel.get_partial_message(old_record.message_id)
                # Edit the original message
                await original_message.edit(view=view)
                new_record = replace(old_record, roll_result=new_result)
                context.message_cache.put(new_record)
                return new_record
        except discord.DiscordException as e:
            log.info("Failed to edit interaction via partial message: %s", e)
        try:
            channel = interaction.channel
            if hasattr(channel, "get_partial_message"):
                original_message = channel.get_partial_message(old_record.message_id)
                # Reply to the original message
                await original_message.reply(view=view)
                new_record = replace(old_record, roll_result=new_result)
                context.message_cache.put(new_record)
                return new_record
        except discord.DiscordException as e:
            log.info("Failed to reply interaction via partial message: %s", e)
        try:
            # Edit the original message
            await interaction.edit_original_response(view=view)
            new_record = replace(old_record, roll_result=new_result)
            context.message_cache.put(new_record)
            log.info("Edited original response")
            return new_record
        except discord.DiscordException as e:
            log.info("Failed to edit original response: %s", e)
        try:
            # Reply the original message
            await interaction.followup.send(view=view)
            new_record = replace(old_record, roll_result=new_result)
            context.message_cache.put(new_record)
            log.info("Followed up to the original response")
            return new_record
        except discord.DiscordException as e:
            log.info("Failed to follow-up: %s", e)

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
        await interaction.response.send_message(view=primary_view)
        record = await self.create_message(label=label, result=result)
        context.message_cache.put(record)
        return record

    async def create_message(self, *, label: str,
                             result: RollRecordBase):
        interaction = self.interaction
        original_message = await interaction.original_response()
        now = datetime.now()
        expires_at = now + timedelta(days=7)
        return MessageRecord(
            message_id=original_message.id,
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id or 0,
            owner_id=interaction.user.id,
            label=label,
            created_at=int(now.timestamp()),
            expires_at=int(expires_at.timestamp()),
            roll_result=result
        )

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
        await interaction.response.defer()

    async def send_as_followup(self, menu: LayoutView):
        followup_message = await self.interaction.followup.send(view=menu, ephemeral=True, wait=True)
        menu.followup_message = followup_message
        # self.followup_message = await interaction.edit_original_response(view=self)
