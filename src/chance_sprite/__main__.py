from __future__ import annotations

import logging
import os
import sys

from .discord_sprite import DiscordSprite
from .file_sprite import ConfigFile


def main() -> None:
    token = ConfigFile[str, str]("discord_secret.json").get("discord_token")
    if not token:
        print("Missing DISCORD_TOKEN env var.", file=sys.stderr)
        raise SystemExit(2)

    bot = DiscordSprite()
    bot.run(token)

if __name__ == "__main__":
    # Set up logging from env
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    )
    main()
