# rolld6_commands.py
from __future__ import annotations

import logging

from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)

async def setup(bot: commands.Bot) -> None:
    group = app_commands.Group(name="rolld6", description="SR5 d6 dice rolling tools.")
    app_commands.allowed_installs(guilds=True, users=True)(group)
    app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)(group)

    # Autodiscover roll type modules and call their register(group, roller)
    from .roll_types import discover_modules
    registered = 0
    for module in discover_modules():
        register = getattr(module, "register", None)
        if register is None:
            continue
        register(group)
        registered += 1

    bot.tree.add_command(group)
    log.info("Registered /%s with %d module(s)", group.name, registered)