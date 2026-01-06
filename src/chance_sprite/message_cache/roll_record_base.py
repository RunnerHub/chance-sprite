from __future__ import annotations

from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

from discord import ui

if TYPE_CHECKING:
    from chance_sprite.sprite_context import ClientContext, InteractionContext


@dataclass(frozen=True, kw_only=True)
class RollRecordBase(ABC):
    @abstractmethod
    def build_view(self, label: str, context) -> Callable[[ClientContext], ui.LayoutView]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def send_edge_menu(cls, record, interaction: InteractionContext):
        raise NotImplementedError
