from __future__ import annotations

from abc import abstractmethod, ABC
from typing import Callable

from discord import ui

from chance_sprite.message_cache.roll_record import RollRecordBase, MessageRecord
from chance_sprite.result_types.hits_result import HitsResult


def build_header(label, colour):
    container = ui.Container(accent_color=colour)
    header = label.strip() if label else ""
    if header:
        container.add_item(ui.TextDisplay(f"### {header}"))
        container.add_item(ui.Separator())
    return container


class GenericResultAccessor[R: RollRecordBase](ABC):
    @abstractmethod
    def get(self, record: MessageRecord[R]) -> HitsResult:
        pass
    @abstractmethod
    def update(self, record: MessageRecord[R], result: HitsResult) -> R:
        pass


class RollAccessor[R: RollRecordBase](GenericResultAccessor):
    def __init__(
            self,
            getter: Callable[[R], HitsResult],
            setter: Callable[[R, HitsResult], R],
    ):
        self._get = getter
        self._set = setter

    def get(self, record: MessageRecord[R]) -> HitsResult:
        return self._get(record.roll_result)

    def update(self, record: MessageRecord[R], value: HitsResult) -> R:
        return self._set(record.roll_result, value)
