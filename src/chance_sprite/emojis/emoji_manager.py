# emoji_manager.py
from __future__ import annotations

import imghdr
import logging
from dataclasses import dataclass
from importlib import resources

import discord

log = logging.getLogger(__name__)

KEYCAPS_0_10 = "0️⃣ 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣ 8️⃣ 9️⃣ 🔟"
UNICODE_D6 = "⚀⚁⚂⚃⚄⚅"
UNICODE_CIRCLE_FILLED = "❶❷❸❹❺❻❼❽❾❿"
UNICODE_CIRCLE_EMPTY = "⓪①②③④⑤⑥⑦⑧⑨⑩"
UNICODE_PARENTHESIZED = "⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽"
UNICODE_SUPER = "⁰"
UNICODE_SUB = "₀"
UNICODE_FULLWIDTH = "０１２３４５６７８９"
UNICODE_FULLSMALL = "０１２３４５６７８９"
UNICODE_PLUSMINUS = "⊕⊖➕➖"
UNICODE_REFRESH = "🔁🔄♻️"
UNICODE_PUSHLIMIT = "🔥💥⚡⬆️"
UNICODE_EXPLODE = "💥🎇"
UNICODE_GLITCH = "⚠❗️🌀💀☠️🛑"

@dataclass(frozen=True)
class EmojiPack:
    d6: list[str]
    d6_ex: list[str]
    d6_limited: list[str]
    d6_glitch: list[str]
    d6_ex_glitch: list[str]
    d6_limited_glitch: list[str]
    reroll: str
    push: str
    btl: str
    close_call: str
    glitch: str
    critical_glitch: str

RAW_TEXT_EMOJI_PACK: EmojiPack = EmojiPack(
    d6=["①", "②", "③", "④", "❺", "❻"],
    d6_ex=["①", "②", "③", "④", "❺", "❻"],
    d6_limited=["~~①~~", "~~②~~", "~~③~~", "~~④~~", "~~❺~~", "~~❻~~"],
    d6_glitch=["⚠", "②", "③", "④", "❺", "❻"],
    d6_ex_glitch=["⚠", "②", "③", "④", "❺", "❻"],
    d6_limited_glitch=["~~⚠~~", "~~②~~", "~~③~~", "~~④~~", "~~❺~~", "~~❻~~"],
    reroll="♻️",
    push="⚡",
    btl="💥",
    close_call="🛡️",
    glitch="⚠",
    critical_glitch="🛑"
)

class EmojiManager:
    def __init__(self, resource: str) -> None:
        self.resource = resource
        self.by_name: dict[str, discord.Emoji] = {}
        self.packs: EmojiPack = RAW_TEXT_EMOJI_PACK

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
        """
        Define your packs by emoji *names*, then resolve to "<:name:id>" strings.
        Fail fast if a required emoji is missing.
        """
        def req(name: str) -> str:
            e = self.by_name.get(name)
            if not e:
                raise KeyError(f"Required emoji not found after sync: {name}")
            return str(e)

        d6r = ["d6r1", "d6r2", "d6r3", "d6r4", "d6r5", "d6r6"]
        d6ex = "d6e6"
        d6l = ["d6l1", "d6l2", "d6l3", "d6l4", "d6l5", "d6l6"]
        d6g1 = "d6g1"
        d6l1g = "d6l1g"

        packs = EmojiPack(
            d6=[req(n) for n in d6r],
            d6_ex=[req(n) for n in d6r[:5]] + [req(d6ex)],
            d6_limited=[req(n) for n in d6l],
            d6_glitch=[req(d6g1)] + [req(n) for n in d6r[1:]],
            d6_ex_glitch=[req(d6g1)] + [req(n) for n in d6r[1:5]] + [req(d6ex)],
            d6_limited_glitch=[req(d6l1g)] + [req(n) for n in d6l[1:]],
            reroll=req("reroll"),
            push="⚡",
            btl="💥",
            close_call="🛡️",
            glitch="glitch",
            critical_glitch="critglitch"
        )
        self.packs = packs
        return packs
