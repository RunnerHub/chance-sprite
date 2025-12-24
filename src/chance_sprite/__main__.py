from __future__ import annotations

import sys

from .discord_sprite import DiscordSprite
from .file_sprite import ConfigFile

def main() -> None:
    token = ConfigFile("discord_secret.json").get("discord_token")
    if not token:
        print("Missing DISCORD_TOKEN env var.", file=sys.stderr)
        raise SystemExit(2)

    bot = DiscordSprite()
    bot.run(token)

if __name__ == "__main__":
    main()
