from __future__ import annotations

from dataclasses import dataclass

from chance_sprite.result_types.hits_result import HitsResult
from chance_sprite.sprite_context import InteractionContext


@dataclass(frozen=True, kw_only=True)
class PushTheLimitHitsResult(HitsResult):
    exploded_dice: tuple[tuple[int, ...], ...]
    rerolled_hits: int

    @property
    def hits_limited(self):
        return self.dice_hits + self.rerolled_hits

    def render_limited_hits(self):
        if self.limit > 0:
            return f" **{self.dice_hits}** hit{'' if self.dice_hits == 1 else 's'} ~~limit {self.limit}~~"
        else:
            return f" **{self.dice_hits}** hit{'' if self.dice_hits == 1 else 's'}"

    def render_roll(self, context: InteractionContext):
        line = super().render_roll(context)
        emojis = context.emoji_manager.packs.d6_ex
        line += f"\n`>push:`" + "".join(emojis[x - 1] for x in self.exploded_dice[0]) + f" **{sum(1 for r in self.exploded_dice[0] if r in (5, 6))}** hits"
        for roll in self.exploded_dice[1:]:
            line += f"\n`explode:`" + "".join(emojis[x - 1] for x in roll) + f" **{sum(1 for r in roll if r in (5, 6))}** hits"
        line += f"\n**{self.hits_limited}** Total Hits"
        return line
