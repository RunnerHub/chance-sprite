# discord_sprite.py

from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands

from chance_sprite.emojis.emoji_manager import EmojiManager
from chance_sprite.file_sprite import (
    ConfigFile,
    RollRecordCacheFile,
    DatabaseHandle,
    MessageRecordStore,
)
from chance_sprite.rollui.roll_view_persist import RollViewPersist
from chance_sprite.sprite_context import ClientContext

log = logging.getLogger(__name__)

EXTENSIONS: tuple[str, ...] = ("chance_sprite.rolld6_commands",)


class DiscordSprite(ClientContext):
    def __init__(self, *, enable_sync: bool = True) -> None:
        self.config = ConfigFile[str, Any]("config.json")
        self.database = DatabaseHandle("chance_sprite.sqlite3")
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(
            emoji_manager=EmojiManager("chance_sprite.emojis"),
            message_cache=MessageRecordStore(self.database),
            command_prefix=commands.when_mentioned,  # unused for slash-only; harmless
            intents=intents,
        )
        old_cache_file = RollRecordCacheFile("message_cache.json")
        old_cache_file.dump(self.message_store)
        self.enable_global_sync = enable_sync
        self.base_command_name = self.config["command_name"]

    async def setup_hook(self) -> None:
        self.add_view(RollViewPersist())
        log.info(f"Global sync: {self.enable_global_sync}")
        self.tree.clear_commands(guild=None)

        if not self.enable_global_sync:
            await self.tree.sync()

        # Load cogs/extensions
        for ext in EXTENSIONS:
            await self.load_extension(ext)

        # Global sync (slow propagation).
        if self.enable_global_sync:
            await self.tree.sync()

        # Fast sync (for testing mainly, causes double command registration if command name matches)
        log.info("Trying fast sync")
        guilds = (
            self.config["fastpush_guilds"] if "fastpush_guilds" in self.config else None
        )
        if guilds:
            for guild_id in self.config["fastpush_guilds"]:
                try:
                    log.info(f"Fast syncing {guild_id}...")
                    guild = discord.Object(id=guild_id)
                    self.tree.copy_global_to(guild=guild)
                    # self.tree.clear_commands(guild=guild)
                    await self.tree.sync(guild=guild)
                    log.info("done.")
                except Exception as e:
                    log.info("errored: %s", e)

    async def on_ready(self) -> None:
        if self.user:
            print(f"Logged in as {self.user} (id={self.user.id})")
        await self.emoji_manager.sync_application_emojis(self)
        self.emoji_manager.build_packs()
        try:
            username = self.config["username"]
            if self.user.name != username:
                log.info(
                    f"attempting to change username from {self.user.name} to {username}"
                )
                await self.user.edit(username=username)
        except Exception as e:
            log.info("caught exception: %s", e)
