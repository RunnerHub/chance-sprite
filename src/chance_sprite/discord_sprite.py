# discord_sprite.py

from __future__ import annotations

import discord
from discord.ext import commands

EXTENSIONS: tuple[str, ...] = (
    "chance_sprite.rolld6_commands",
)

class DiscordSprite(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(
            command_prefix=commands.when_mentioned,  # unused for slash-only; harmless
            intents=intents,
        )

    async def setup_hook(self) -> None:
        # Load cogs/extensions
        for ext in EXTENSIONS:
            await self.load_extension(ext)

        # Global sync (slow propagation).
        await self.tree.sync()

        # TODO: instant sync per guild
        # Instant sync to one guild
        # guild = discord.Object(id=TEST_GUILD_ID)
        # self.tree.copy_global_to(guild=guild)
        # await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (id={self.user.id})")