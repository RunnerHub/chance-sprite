from typing import Callable

from chance_sprite.message_cache.roll_record_base import RollRecordBase
from chance_sprite.result_types.hits_result import HitsResult


class RollAccessor[R: RollRecordBase]:
    def __init__(
        self,
        getter: Callable[[R], HitsResult],
        setter: Callable[[R, HitsResult], R],
    ):
        self._get = getter
        self._set = setter

    def get(self, roll: R) -> HitsResult:
        return self._get(roll)

    def update(self, roll: R, new_result: HitsResult) -> R:
        return self._set(roll, new_result)
