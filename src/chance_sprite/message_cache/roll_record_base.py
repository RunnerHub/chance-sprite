from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from discord import ui

if TYPE_CHECKING:
    from chance_sprite.message_cache.message_record import MessageRecord
    from chance_sprite.sprite_context import InteractionContext


@dataclass(frozen=True, kw_only=True)
class RollRecordBase(ABC):
    @abstractmethod
    def build_view(self, label: str, context: InteractionContext) -> ui.LayoutView:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def send_menu(cls, record: MessageRecord, context: InteractionContext):
        raise NotImplementedError

    def current_owners(self, record: MessageRecord, context: InteractionContext):
        return [record.owner_id]


@dataclass(frozen=True, kw_only=True)
class ResistableRoll(RollRecordBase):
    resistable: bool = True

    @abstractmethod
    def already_resisted(self) -> list[int]:
        raise NotImplementedError

    @abstractmethod
    def resistance_target(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def resist(
        self, context: InteractionContext, dice: int, limit: int, pre_edge: bool
    ) -> ResistableRoll:
        raise NotImplementedError
