# discord_sprite.py

from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands

from chance_sprite.file_sprite import ConfigFile
from chance_sprite.sprite_context import SpriteContext
from chance_sprite.ui.edge_menu_persist import EdgeMenuPersist

log = logging.getLogger(__name__)

EXTENSIONS: tuple[str, ...] = (
    "chance_sprite.rolld6_commands",
)


class DiscordSprite(commands.Bot):
    def __init__(self, *, enable_sync: bool = True) -> None:
        self.config = ConfigFile[str, Any]("config.json")
        self.context = SpriteContext()
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(
            command_prefix=commands.when_mentioned,  # unused for slash-only; harmless
            intents=intents,
        )
        self.enable_global_sync = enable_sync

    async def setup_hook(self) -> None:
        self.add_view(EdgeMenuPersist(self.context))

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
