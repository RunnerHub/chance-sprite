# emoji_manager.py
from __future__ import annotations

import imghdr
import logging
from dataclasses import dataclass
from importlib import resources

import discord

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class EmojiPack:
    d6: list[str]
    d6_ex: list[str]
    edge: list[str]
    glitch: tuple[str, str, str]


EMPTY_EMOJI_PACK: EmojiPack = EmojiPack(
    d6=[],
    d6_ex=[],
    edge=[],
    glitch=("", "", "")
)

RAW_TEXT_EMOJI_PACK: EmojiPack = EmojiPack(
    d6=[str(n + 1) for n in range(6)],
    d6_ex=[str(n + 1) for n in range(6)],
    edge=["reroll", "push", "second_chance"],
    glitch=("", "glitch", "critglitch")
)

class EmojiManager:
    def __init__(self, resource: str) -> None:
        self.resource = resource
        self.by_name: dict[str, discord.Emoji] = {}
        self.packs: EmojiPack = EMPTY_EMOJI_PACK

    @property
    def loaded(self) -> bool:
        return not self.packs is EMPTY_EMOJI_PACK

    def iter_emoji_assets(self):
        base = resources.files(self.resource)
        for p in base.iterdir():
            if not p.is_file():
                continue
            data = p.read_bytes()
            if imghdr.what(None, data):
                yield p.name.rsplit(".", 1)[0], data

    async def sync_application_emojis(self, client: discord.Client) -> None:
        # 1) Fetch existing app emojis
        existing = await client.fetch_application_emojis()
        existing_by_name = {e.name: e for e in existing}
        log.info("Application emojis currently: %d", len(existing_by_name))

        # 2) Upload missing ones
        uploaded = 0
        for name, image_bytes in self.iter_emoji_assets():
            if name in existing_by_name:
                continue

            # NOTE: application emojis have size limits. If uploads fail,
            # it’s usually file too large or invalid format.
            try:
                e = await client.create_application_emoji(name=name, image=image_bytes)
            except discord.HTTPException as ex:
                log.error("Failed to upload emoji %s: %s", name, ex)
                continue

            existing_by_name[name] = e
            uploaded += 1
            log.info("Uploaded application emoji: %s (%s)", name, e.id)

        # 3) Refresh mapping (fetch again so we have authoritative list)
        if uploaded:
            existing = await client.fetch_application_emojis()
            existing_by_name = {e.name: e for e in existing}

        self.by_name = existing_by_name
        log.info("Emoji sync complete. Uploaded: %d. Total now: %d", uploaded, len(self.by_name))

    def build_packs(self) -> EmojiPack:
        if self.loaded:
            return self.packs
        """
        Define your packs by emoji *names*, then resolve to "<:name:id>" strings.
        Fail fast if a required emoji is missing.
        """
        def req(name: str) -> str:
            e = self.by_name.get(name)
            if not e:
                raise KeyError(f"Required emoji not found after sync: {name}")
            return str(e)

        d6_names = ["d6r1", "d6r2", "d6r3", "d6r4", "d6r5", "d6r6"]
        d6_ex_names = ["d6r1", "d6r2", "d6r3", "d6r4", "d6r5", "d6r6ex"]
        edge_names = ["reroll"]

        packs = EmojiPack(
            d6=[req(n) for n in d6_names],
            d6_ex=[req(n) for n in d6_ex_names],
            edge=[req(n) for n in edge_names],
            glitch=("", req("glitch"), req("critglitch")),
        )
        self.packs = packs
        return packs
