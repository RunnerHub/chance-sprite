# discord_sprite.py

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from chance_sprite.emojis.emoji_manager import EmojiManager

log = logging.getLogger(__name__)

EXTENSIONS: tuple[str, ...] = (
    "chance_sprite.rolld6_commands",
)

class DiscordSprite(commands.Bot):
    def __init__(self, *, enable_sync: bool = True) -> None:
        self.config = None
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(
            command_prefix=commands.when_mentioned,  # unused for slash-only; harmless
            intents=intents,
        )
        self.emoji_manager = EmojiManager("chance_sprite.emojis")
        self.enable_global_sync = enable_sync

    async def setup_hook(self) -> None:
        # Load cogs/extensions
        for ext in EXTENSIONS:
            await self.load_extension(ext)

        # Global sync (slow propagation).
        if self.enable_global_sync:
            await self.tree.sync()
        #
        # try:
        #     self.config = ConfigFile("config.json")
        #     log.info("Trying fast sync")
        #     for guild_id in self.config["fastpush_guilds"]:
        #         try:
        #             log.info(f"Fast syncing {guild_id}...")
        #             guild = discord.Object(id=guild_id)
        #             self.tree.copy_global_to(guild=guild)
        #             await self.tree.sync(guild=guild)
        #             log.info(f"done.")
        #         except Exception as e:
        #             log.info(f"errored: {e}")
        # except Exception as e:
        #     log.info(f"Config file not found: {e}")

    async def on_ready(self) -> None:
        if self.user:
            print(f"Logged in as {self.user} (id={self.user.id})")
        await self.emoji_manager.sync_application_emojis(self)
