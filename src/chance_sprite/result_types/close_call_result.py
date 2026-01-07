from __future__ import annotations

from dataclasses import dataclass

from chance_sprite.result_types.hits_result import HitsResult
from . import Glitch
from ..sprite_context import InteractionContext


@dataclass(frozen=True, kw_only=True)
class CloseCallResult(HitsResult):
    def render_glitch(self, context: InteractionContext):
        if self.glitch == Glitch.GLITCH:
            return "```diff\n+Glitch Negated```"
        if self.glitch == Glitch.CRITICAL:
            return "```diff\n-Glitch! (Downgraded from Critical Glitch)```"
        return ""
