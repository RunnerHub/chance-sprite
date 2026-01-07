# discord_sprite.py

from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands

from chance_sprite.emojis.emoji_manager import EmojiManager
from chance_sprite.file_sprite import ConfigFile, RollRecordCacheFile, DatabaseHandle, MessageRecordStore
from chance_sprite.rollui.edge_menu_persist import EdgeMenuPersist
from chance_sprite.sprite_context import ClientContext

log = logging.getLogger(__name__)

EXTENSIONS: tuple[str, ...] = (
    "chance_sprite.rolld6_commands",
)


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
        old_cache_file.dump(self.message_cache)
        self.enable_global_sync = enable_sync

    async def setup_hook(self) -> None:
        self.add_view(EdgeMenuPersist())

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
        await self.emoji_manager.sync_application_emojis(self)
        self.emoji_manager.build_packs()
