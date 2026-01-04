from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import discord

from chance_sprite.message_cache.roll_record_base import RollRecordBase


@dataclass(frozen=True, kw_only=True)
class MessageRecord[R: RollRecordBase]:
    message_id: int
    guild_id: int | None
    channel_id: int
    owner_id: int
    label: str
    created_at: int
    expires_at: int
    roll_result: R

    @staticmethod
    async def create_from_interaction(*, interaction: discord.Interaction, label: str,
                                      result: RollRecordBase) -> MessageRecord:
        original_message = await interaction.original_response()
        now = datetime.now()
        expires_at = now + timedelta(days=7)
        return MessageRecord(
            message_id=original_message.id,
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id or 0,
            owner_id=interaction.user.id,
            label=label,
            created_at=int(now.timestamp()),
            expires_at=int(expires_at.timestamp()),
            roll_result=result
        )
