from __future__ import annotations

from dataclasses import dataclass

from chance_sprite.message_cache.roll_record_base import RollRecordBase


@dataclass(frozen=True, kw_only=True)
class MessageRecord [R: RollRecordBase]:
    message_id: int
    guild_id: int | None
    channel_id: int
    owner_id: int
    label: str
    created_at: int
    expires_at: int
    roll_result: R
