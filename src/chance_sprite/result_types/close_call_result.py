from __future__ import annotations

from dataclasses import dataclass

from chance_sprite.emojis.emoji_manager import EmojiPack
from chance_sprite.result_types.hits_result import HitsResult
from . import Glitch


@dataclass(frozen=True, kw_only=True)
class CloseCallResult(HitsResult):
    def render_glitch(self, *, emoji_packs: EmojiPack):
        if self.glitch == Glitch.GLITCH:
            return "```diff\n+Glitch Negated```"
        if self.glitch == Glitch.CRITICAL:
            return "```diff\n-Glitch! (Downgraded from Critical Glitch)```"
        return ""
