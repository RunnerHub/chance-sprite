from __future__ import annotations

from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING

from discord import ui

if TYPE_CHECKING:
    from chance_sprite.sprite_context import InteractionContext


@dataclass(frozen=True, kw_only=True)
class RollRecordBase(ABC):
    @abstractmethod
    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def send_edge_menu(cls, record, context: InteractionContext):
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class ResistableRoll(RollRecordBase):
    resistable: bool = True

    @abstractmethod
    def resistance_target(self) -> int:
        raise NotImplementedError
