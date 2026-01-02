from __future__ import annotations

import random
from dataclasses import dataclass, asdict

from chance_sprite.common.common import Glitch, _default_random
from chance_sprite.common.result_types.hits_result import HitsResult
from chance_sprite.emojis.emoji_manager import EmojiPacks


@dataclass(frozen=True)
class CloseCallResult(HitsResult):
    def render_glitch(self, *, emoji_packs: EmojiPacks):
        if self.glitch == Glitch.GLITCH:
            return "```diff\n+Glitch Negated```"
        if self.glitch == Glitch.CRITICAL:
            return "```diff\n-Glitch! (Downgraded from Critical Glitch)```"
        return ""

    @staticmethod
    def from_hitsresult(hits_result: HitsResult, rng: random.Random = _default_random):
        return CloseCallResult(**asdict(hits_result))