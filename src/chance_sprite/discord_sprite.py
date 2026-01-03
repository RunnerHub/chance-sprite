# discord_sprite.py

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

import discord
from discord.abc import Messageable
from discord.ext import commands

from chance_sprite.emojis.emoji_manager import EmojiManager
from chance_sprite.file_sprite import ConfigFile, RollRecordCacheFile
from chance_sprite.message_cache.roll_record import MessageRecord, RollRecordBase

log = logging.getLogger(__name__)

EXTENSIONS: tuple[str, ...] = (
    "chance_sprite.rolld6_commands",
)


class SpriteContext:
    def __init__(self, client: discord.Client) -> None:

        self.client = client
        self.emoji_manager = EmojiManager("chance_sprite.emojis")
        self.message_cache = RollRecordCacheFile("message_cache.json")

    async def update_message(self, old_record: MessageRecord, new_result: RollRecordBase,
                             interaction: discord.Interaction):
        view_builder = new_result.build_view(old_record.label)
        emojis = self.emoji_manager.packs
        if not emojis:
            return
        view = view_builder(emojis)
        channel = interaction.channel
        if channel is None or not isinstance(channel, Messageable):
            raise RuntimeError("Interaction has no message-capable channel")
        original_message = await channel.fetch_message(old_record.message_id)
        # Edit the original message that contains this view
        await original_message.edit(view=view)
        new_record = replace(old_record, roll_result=new_result)
        self.message_cache.put(new_record)
        return new_record


class DiscordSprite(commands.Bot):
    def __init__(self, *, enable_sync: bool = True) -> None:
        self.config = ConfigFile[str, Any]("config.json")
        self.context = SpriteContext(self)
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(
            command_prefix=commands.when_mentioned,  # unused for slash-only; harmless
            intents=intents,
        )
        self.enable_global_sync = enable_sync

    async def setup_hook(self) -> None:
        # Load cogs/extensions
        for ext in EXTENSIONS:
            await self.load_extension(ext)

        # Global sync (slow propagation).
        if self.enable_global_sync:
            await self.tree.sync()

        # Undo guild sync
        log.info("Trying fast sync")
        for guild_id in self.config["fastpush_guilds"]:
            try:
                log.info(f"Fast syncing {guild_id}...")
                guild = discord.Object(id=guild_id)
                # self.tree.copy_global_to(guild=guild)
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
                log.info(f"done.")
            except Exception as e:
                log.info(f"errored: {e}")

    async def on_ready(self) -> None:
        if self.user:
            print(f"Logged in as {self.user} (id={self.user.id})")
        await self.context.emoji_manager.sync_application_emojis(self)
        self.context.emoji_manager.build_packs()
