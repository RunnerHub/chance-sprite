from __future__ import annotations

from dataclasses import dataclass

from chance_sprite.sprite_context import InteractionContext


@dataclass(frozen=True, kw_only=True)
class AdditiveResult:
    dice: int
    rolls: tuple[int, ...]

    @property
    def total_roll(self):
        return sum(r for r in self.rolls)

    def render_dice(self, context: InteractionContext) -> str:
        emojis = context.emoji_manager.packs.d6
        line = "".join(emojis[x - 1] for x in self.rolls)
        return line