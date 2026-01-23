# discord_sprite.py

from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands

from chance_sprite.emojis.emoji_manager import EmojiManager
from chance_sprite.file_sprite import (
    CacheFile,
    ConfigFile,
    DatabaseHandle,
    MessageRecordStore,
    UserAvatarStore,
)
from chance_sprite.message_cache.webhook_handle import WebhookHandle
from chance_sprite.rollui.roll_view_persist import RollViewPersist

log = logging.getLogger(__name__)

EXTENSIONS: tuple[str, ...] = ("chance_sprite.command_loader",)


def _intents():
    # TODO: minimal intents
    return discord.Intents.default()


class DiscordSprite(commands.Bot):
    def __init__(self, *, enable_sync: bool = True) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,  # unused for slash-only; harmless
            intents=_intents(),
        )
        self.config = ConfigFile[str, Any]("config.json")
        self.database = DatabaseHandle("chance_sprite.sqlite3")
        heavy_emojis = EmojiManager("chance_sprite.emojis")
        lite_emojis = EmojiManager("chance_sprite.emojis")

        self.emoji_manager = heavy_emojis
        self.lite_emojis = lite_emojis
        self.message_store = MessageRecordStore(self.database)
        self.message_handles: dict[int, discord.InteractionMessage] = dict()
        self.webhook_handles = CacheFile[int, WebhookHandle]("webhook_cache.json")
        self.base_command_name = None
        self.user_avatar_store = UserAvatarStore(self.database)
        self.enable_global_sync = enable_sync
        self.base_command_name = self.config["command_name"]

    async def setup_hook(self) -> None:
        self.add_view(RollViewPersist())
        log.info(f"Global sync: {self.enable_global_sync}")
        self.tree.clear_commands(guild=None)

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

        if not self.enable_global_sync:
            await self.tree.sync()

        # Load cogs/extensions
        for ext in EXTENSIONS:
            await self.load_extension(ext)

        # Global sync (slow propagation).
        if self.enable_global_sync:
            await self.tree.sync()

    async def on_ready(self) -> None:
        if self.user:
            print(f"Logged in as {self.user} (id={self.user.id})")
        await self.emoji_manager.sync_application_emojis(self)
        self.emoji_manager.build_packs()
        try:
            username = self.config.get("username")
            if self.user and username and self.user.name != username:
                log.info(
                    f"attempting to change username from {self.user.name} to {username}"
                )
                await self.user.edit(username=username)
        except Exception as e:
            log.info("caught exception: %s", e)
