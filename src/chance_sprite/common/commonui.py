from __future__ import annotations

from abc import abstractmethod
from typing import Callable

from discord import ui

from chance_sprite.common.result_types.hits_result import HitsResult
from chance_sprite.emojis.emoji_manager import EmojiPacks


@staticmethod
def build_header(label, colour):
    container = ui.Container(accent_color=colour)
    header = label.strip() if label else ""
    if header:
        container.add_item(ui.TextDisplay(f"### {header}"))
        container.add_item(ui.Separator())
    return container


BuildViewFn = Callable[[EmojiPacks], ui.LayoutView]


class GenericResultAccessor:
    @abstractmethod
    def get(self) -> HitsResult:
        pass
    @abstractmethod
    async def update(self, result: HitsResult) -> None:
        pass
