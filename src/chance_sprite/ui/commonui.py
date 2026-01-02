from __future__ import annotations

from abc import abstractmethod, ABC
from typing import Callable

from discord import ui

from chance_sprite.emojis.emoji_manager import EmojiPacks
from chance_sprite.result_types.hits_result import HitsResult


def build_header(label, colour):
    container = ui.Container(accent_color=colour)
    header = label.strip() if label else ""
    if header:
        container.add_item(ui.TextDisplay(f"### {header}"))
        container.add_item(ui.Separator())
    return container


BuildViewFn = Callable[[EmojiPacks], ui.LayoutView]


class GenericResultAccessor(ABC):
    @abstractmethod
    def get(self) -> HitsResult:
        pass
    @abstractmethod
    async def update(self, result: HitsResult) -> None:
        pass
