from __future__ import annotations

from dataclasses import dataclass
from typing import List

from chance_sprite.emojis.emoji_manager import EmojiPack


@dataclass(frozen=True, kw_only=True)
class AdditiveResult:
    dice: int
    rolls: List[int]

    @property
    def total_roll(self):
        return sum(r for r in self.rolls)

    def render_dice(self, *, emoji_packs: EmojiPack) -> str:
        emojis = emoji_packs.d6
        line = "".join(emojis[x - 1] for x in self.rolls)
        return line