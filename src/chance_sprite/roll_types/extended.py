# extended.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Callable

from discord import app_commands, Interaction
from discord import ui

from chance_sprite.result_types import HitsResult
from chance_sprite.roller import roll_hits
from ..message_cache import message_codec
from ..message_cache.message_record import MessageRecord
from ..message_cache.roll_record_base import RollRecordBase
from ..rollui.commonui import build_header
from ..rollui.edge_menu_persist import EdgeMenuButton
from ..sprite_context import ClientContext, InteractionContext


@dataclass(frozen=True)
class ExtendedIteration:
    n: int
    roll: HitsResult
    cumulative_hits: int


@message_codec.alias("ExtendedResult")
@dataclass(frozen=True)
class ExtendedRoll(RollRecordBase):
    start_dice: int
    threshold: int
    max_iters: int
    iterations: List[ExtendedIteration]
    succeeded: bool
    final_hits: int
    iters_used: int
    limit: int
    gremlins: int

    @staticmethod
    def roll(dice: int, threshold: int, max_iters: int, limit: int, gremlins: int) -> ExtendedRoll:
        iterations: List[ExtendedIteration] = []
        cumulative = 0
        iters_used = 0

        for i in range(1, max_iters + 1):
            pool = dice - (i - 1)
            if pool < 1:
                break

            r = roll_hits(pool, limit=limit, gremlins=gremlins)
            cumulative += r.hits_limited
            iters_used += 1
            iterations.append(ExtendedIteration(n=i, roll=r, cumulative_hits=cumulative))

            if cumulative >= threshold:
                break

        return ExtendedRoll(
            start_dice=dice,
            threshold=threshold,
            max_iters=max_iters,
            iterations=iterations,
            succeeded=(cumulative >= threshold),
            final_hits=cumulative,
            iters_used=iters_used,
            limit=limit,
            gremlins=gremlins
        )

    def build_view(self, label: str) -> Callable[[ClientContext], ui.LayoutView]:
        def _build(context: ClientContext) -> ui.LayoutView:
            accent = 0x88FF88 if self.succeeded else 0xFF8888
            menu_button = EdgeMenuButton()
            container = build_header(menu_button, label, accent)

            container.add_item(
                ui.TextDisplay(
                    f"Extended test: start **{self.start_dice}** dice, threshold **{self.threshold}**, max **{self.max_iters}** roll(s)\n"
                )
            )

            container.add_item(ui.Separator())

            # Pack iterations into as few TextDisplays as possible to respect the ~30 component limit.
            blocks: list[str] = []
            prev = 0
            for it in self.iterations:
                blocks.append(
                    f"`{it.roll.dice}d6` {it.roll.render_dice(emoji_packs=context.emoji_manager.packs)} [{prev}+**{it.roll.hits_limited}**=**{it.cumulative_hits}**]"
                )
                prev = it.cumulative_hits

            # Split into chunks
            chunk = ""
            for b in blocks:
                candidate = (chunk + "\n" + b).strip() if chunk else b
                if len(candidate) > 1800:  # keep headroom
                    container.add_item(ui.TextDisplay(chunk))
                    chunk = b
                else:
                    chunk = candidate

            if chunk:
                container.add_item(ui.TextDisplay(chunk))

            container.add_item(ui.Separator())
            container.add_item(
                ui.TextDisplay(
                    f"Result: **{'Succeeded' if self.succeeded else 'Failed'}** after **{self.iters_used}** interval{"s" if self.iters_used != 1 else ""} with {self.final_hits} total hits (**{self.final_hits - self.threshold}** net)"
                )
            )

            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            return view
        return _build

    @classmethod
    async def send_edge_menu(cls, record: MessageRecord, context: InteractionContext):
        pass


def register(group: app_commands.Group) -> None:
    @group.command(name="extended", description="Extended roll: repeated tests with shrinking dice pool.")
    @app_commands.describe(
        label="A label to describe the roll.",
        dice="Starting dice pool (1-99).",
        threshold="Total hits needed (>=1).",
        max_iters="Maximum number of rolls (1-99).",
        limit="Limit applicable to each roll.",
        gremlins="Reduce the number of 1s required for a glitch."
    )
    async def cmd(
            interaction: Interaction[ClientContext],
        label: str,
        dice: app_commands.Range[int, 1, 99],
        threshold: app_commands.Range[int, 1, 99],
        max_iters: app_commands.Range[int, 1, 99] = 10,
        limit: Optional[app_commands.Range[int, 1, 99]] = None,
        gremlins: Optional[app_commands.Range[int, 1, 99]] = None
    ) -> None:
        result = ExtendedRoll.roll(int(dice), int(threshold), int(max_iters), limit=limit or 0, gremlins=gremlins or 0)
        await InteractionContext(interaction).transmit_result(label=label, result=result)
