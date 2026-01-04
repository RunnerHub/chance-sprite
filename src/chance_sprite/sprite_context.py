from __future__ import annotations

import logging
from dataclasses import replace

import discord
from discord import ui
from discord.abc import Messageable

from chance_sprite.emojis.emoji_manager import EmojiManager
from chance_sprite.file_sprite import RollRecordCacheFile
from chance_sprite.message_cache.message_record import MessageRecord
from chance_sprite.message_cache.roll_record_base import RollRecordBase

log = logging.getLogger(__name__)


class SpriteContext:
    def __init__(self) -> None:
        self.emoji_manager = EmojiManager("chance_sprite.emojis")
        self.message_cache = RollRecordCacheFile("message_cache.json")
        log.info(f"Loaded {len(self.message_cache.data)} messages like {self.message_cache.data}")

    async def update_message(self, old_record: MessageRecord, new_result: RollRecordBase,
                             interaction: discord.Interaction):
        log.info(f"Updating message in Channel {interaction.channel_id}: {interaction.channel}")
        view_builder = new_result.build_view(old_record.label)
        emojis = self.emoji_manager.packs
        if not emojis:
            return
        view = view_builder(self)
        # # Doesn't seem to ever work
        # try:
        #     await interaction.message.edit(view=view)
        #     await interaction.defer()
        # except discord.DiscordException:
        #     log.info("Failed to edit interaction via interaction message object")
        try:
            channel = interaction.channel
            if channel is None or not isinstance(channel, Messageable):
                raise RuntimeError("Interaction has no message-capable channel")
            original_message = channel.get_partial_message(old_record.message_id)
            # Edit the original message
            await original_message.edit(view=view)
            new_record = replace(old_record, roll_result=new_result)
            self.message_cache.put(new_record)
            return new_record
        except discord.DiscordException as e:
            log.info("Failed to edit interaction via partial message: %s", e)
        try:
            channel = interaction.channel
            original_message = channel.get_partial_message(old_record.message_id)
            # Reply to the original message
            await original_message.reply(view=view)
            new_record = replace(old_record, roll_result=new_result)
            self.message_cache.put(new_record)
            return new_record
        except discord.DiscordException as e:
            log.info("Failed to reply interaction via partial message: %s", e)
        try:
            # Edit the original message
            await interaction.edit_original_response(view=view)
            new_record = replace(old_record, roll_result=new_result)
            self.message_cache.put(new_record)
            log.info("Edited original response")
            return new_record
        except discord.DiscordException as e:
            log.info("Failed to edit original response: %s", e)
        try:
            # Reply the original message
            await interaction.followup.send(view=view)
            new_record = replace(old_record, roll_result=new_result)
            self.message_cache.put(new_record)
            log.info("Followed up to the original response")
            return new_record
        except discord.DiscordException as e:
            log.info("Failed to follow-up: %s", e)

    async def transmit_result(self, label: str, result: RollRecordBase, interaction: discord.Interaction):
        # TODO: await emoji sync and update
        if self.emoji_manager.loaded:
            view_builder = result.build_view(label)
            primary_view = view_builder(self)
        else:
            primary_view = ui.LayoutView()
            primary_view.add_item(ui.TextDisplay("Still loading emojis, please wait!"))
        await interaction.response.send_message(view=primary_view)
        record = await MessageRecord.create_from_interaction(interaction=interaction, label=label, result=result)
        self.message_cache.put(record)
        return record

    async def transmit_result_from_interaction(self, interaction: discord.Interaction):
        if not interaction.message:
            log.error(f"Couldn't find message on transmitted interaction: {interaction}")
        else:
            message_id = interaction.message.id
            message_record = self.message_cache[message_id]
            label = message_record.label
            result = message_record.roll_result
            await self.transmit_result(label, result, interaction)
        await interaction.response.defer()
