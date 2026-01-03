from __future__ import annotations

from abc import abstractmethod, ABC
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

import discord
from discord import ui

from chance_sprite.emojis.emoji_manager import EmojiPacks


@dataclass(frozen=True, kw_only=True)
class RollRecordBase(ABC):
    @abstractmethod
    def build_view(self, label: str) -> Callable[[EmojiPacks], ui.LayoutView]:
        raise NotImplementedError


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
    async def from_interaction(*, interaction: discord.Interaction, label: str,
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
