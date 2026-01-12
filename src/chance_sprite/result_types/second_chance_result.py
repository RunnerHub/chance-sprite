from __future__ import annotations

import random
from dataclasses import dataclass, replace

from chance_sprite.result_types.hits_result import HitsResult

from ..sprite_context import InteractionContext
from ..sprite_utils import Glitch, _default_random, limit_mask


@dataclass(frozen=True, kw_only=True)
class SecondChanceHitsResult(HitsResult):
    rerolled_dice: tuple[int, ...]
    rerolled_hits: int

    @property
    def hits_limited(self):
        total_hits = self.dice_hits + self.rerolled_hits
        if self.limit > 0:
            return min(self.limit, total_hits)
        else:
            return total_hits

    def render_limited_rerolled_hits(self):
        total_hits = self.dice_hits + self.rerolled_hits
        if self.limit > 0:
            if total_hits > self.limit:
                return f" ~~{total_hits} hit{'' if total_hits == 1 else 's'}~~ limit **{self.limit}**"
            else:
                return f" **{total_hits}** hit{'' if total_hits == 1 else 's'} ~~limit {self.limit}~~"
        else:
            return f" **{total_hits}** hit{'' if total_hits == 1 else 's'}"

    def get_dice_mask(self):
        all_dice_for_mask = (
            self.rolls[: self.dice] + self.rerolled_dice[: self.dice - self.dice_hits]
        )
        return limit_mask(self.limit, all_dice_for_mask)

    def render_roll(self, context: InteractionContext):
        line = super().render_roll(context)
        line += (
            f"\n+{context.emoji_manager.packs.reroll}"
            + self.render_rerolls(context)
            + self.render_limited_rerolled_hits()
        )
        return line

    def render_rerolls(self, context: InteractionContext) -> str:
        packs = context.emoji_manager.packs
        chosen_emojis = (
            packs.d6
            if (self.glitch == Glitch.NONE)
            else context.emoji_manager.packs.d6_glitch
        )
        limited_emojis = (
            packs.d6_limited
            if (self.glitch == Glitch.NONE)
            else context.emoji_manager.packs.d6_limited_glitch
        )

        adjusted_rolls = self.rerolled_dice[: self.dice - self.dice_hits]
        baleeted_dice = self.rerolled_dice[self.dice - self.dice_hits :]
        mask = self.get_dice_mask()

        reroll_mask = mask[self.dice :] if mask else None

        dice_emojis = [
            chosen_emojis[x - 1]
            if not reroll_mask or reroll_mask[i]
            else limited_emojis[x - 1]
            for (i, x) in enumerate(adjusted_rolls)
        ]

        n_original_hits = sum(
            1 for r in self.rolls[: self.original_dice] if r in (5, 6)
        )
        n_original_rerolls = self.original_dice - n_original_hits
        n_current_rerolls = self.dice - self.dice_hits
        post_dice_adjustment = n_current_rerolls - n_original_rerolls
        if post_dice_adjustment < 0:
            line = "".join(dice_emojis)
            line += (
                "-~~"
                + "".join(str(x) for x in baleeted_dice[:n_original_rerolls])
                + "~~"
            )
        else:
            line = "".join(dice_emojis[:n_original_rerolls])

        if len(self.rerolled_dice) > n_original_rerolls:
            if post_dice_adjustment > 0:
                line += "+" + "".join(dice_emojis[n_original_rerolls:n_current_rerolls])
            if len(self.rerolled_dice) > n_current_rerolls:
                line += (
                    "-~~"
                    + "".join(str(x) for x in baleeted_dice[n_original_rerolls:])
                    + "~~"
                )
        return line

    def adjust_dice(self, adjustment: int, rng: random.Random = _default_random):
        replacement_base = super().adjust_dice(adjustment, rng)
        added_dice_amount = (
            replacement_base.dice - replacement_base.dice_hits - len(self.rerolled_dice)
        )
        added_rerolls = tuple(rng.randint(1, 6) for _ in range(added_dice_amount))
        new_rerolled_dice = self.rerolled_dice + added_rerolls
        new_rerolled_hits = sum(
            1
            for r in new_rerolled_dice[
                0 : replacement_base.dice - replacement_base.dice_hits
            ]
            if r in (5, 6)
        )
        return replace(
            replacement_base,
            rerolled_dice=new_rerolled_dice,
            rerolled_hits=new_rerolled_hits,
        )
