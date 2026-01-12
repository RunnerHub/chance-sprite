# sprite_utils.py$
from __future__ import annotations

import logging
from datetime import timedelta
from enum import Enum
import random
from typing import Protocol, TypeGuard, runtime_checkable

import discord

log = logging.getLogger(__name__)


class HasNetHits(Protocol):
    net_hits: int


def normalize_key(raw_text: str) -> str:
    # Casefold + remove separators, so "pre-edge" matches "preedge"
    return "".join(
        character for character in raw_text.casefold().strip() if character.isalnum()
    )


def levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    if len(left) > len(right):
        left, right = right, left

    previous_row = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current_row = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            insertion = current_row[right_index - 1] + 1
            deletion = previous_row[right_index] + 1
            substitution = previous_row[right_index - 1] + (left_char != right_char)
            current_row.append(min(insertion, deletion, substitution))
        previous_row = current_row
    return previous_row[-1]


def split_argstr(args_text: str) -> list[str]:
    # comma-separated tokens
    return [token.strip() for token in args_text.split(",") if token.strip()]


def parse_int(s: str | None, default: int | None = None) -> int | None:
    try:
        return int(s) if s is not None else default
    except ValueError:
        return default


def plural_s(n, s: str = "s"):
    if n == 1:
        return ""
    else:
        return s


def sign_int(n):
    if n >= 0:
        return "+" + str(n)
    else:
        return str(n)


def humanize_timedelta(td: timedelta) -> str:
    seconds = int(td.total_seconds())
    parts = []

    weeks, seconds = divmod(seconds, 604800)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if weeks:
        parts.append(f"{weeks} week{plural_s(weeks)}")
    if days:
        parts.append(f"{days} day{plural_s(days)}")
    if hours:
        parts.append(f"{hours} hour{plural_s(hours)}")
    if minutes:
        parts.append(f"{minutes} minute{plural_s(minutes)}")
    if not parts:
        parts.append(f"{seconds} second{plural_s(seconds)}")

    return ", ".join(parts)


def color_by_net_hits(net: int):
    # Color by outcome
    if net > 0:
        accent = 0x88FF88
    elif net < 0:
        accent = 0xFF8888
    else:
        accent = 0x8888FF
    return accent


def limit_mask(limit, rolls):
    if limit <= 0 or limit >= len(rolls):
        return None
    num_chosen = 0
    mask = [False for _ in rolls]
    for value in [6, 5, 4, 3, 2, 1]:
        for i, el in enumerate(rolls):
            if el == value:
                mask[i] = True
                num_chosen += 1
                if num_chosen >= limit:
                    return mask


@runtime_checkable
class PartialMessageable(Protocol):
    def get_partial_message(self, message_id: int) -> discord.PartialMessage: ...


def has_get_partial_message(ch: object) -> TypeGuard[PartialMessageable]:
    return isinstance(ch, PartialMessageable)


class Glitch(Enum):
    NONE = "none"
    GLITCH = "glitch"
    CRITICAL = "critical"


_default_random = random.Random()
