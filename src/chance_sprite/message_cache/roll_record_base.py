from __future__ import annotations

from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

import discord
from discord import ui

if TYPE_CHECKING:
    from chance_sprite.sprite_context import SpriteContext


@dataclass(frozen=True, kw_only=True)
class RollRecordBase(ABC):
    @abstractmethod
    def build_view(self, label: str) -> Callable[[SpriteContext], ui.LayoutView]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    async def send_edge_menu(record, context: SpriteContext, interaction: discord.Interaction):
        raise NotImplementedError
