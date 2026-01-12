from __future__ import annotations

import argparse
import logging
import os
import sys

from .discord_sprite import DiscordSprite
from .file_sprite import ConfigFile

log = logging.getLogger(__name__)


def main(sync) -> None:
    token = ConfigFile[str, str]("discord_secret.json").get("discord_token")
    if not token:
        print("Missing DISCORD_TOKEN env var.", file=sys.stderr)
        raise SystemExit(2)

    log.info(f"global command sync: {sync}")
    bot = DiscordSprite(enable_sync=sync)
    bot.run(token)


if __name__ == "__main__":
    # Set up logging from env
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--global-sync",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    args = parser.parse_args()

    main(args.global_sync)
