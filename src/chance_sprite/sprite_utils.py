# sprite_utils.py$
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def normalize_key(raw_text: str) -> str:
    # Casefold + remove separators, so "pre-edge" matches "preedge"
    return "".join(character for character in raw_text.casefold().strip() if character.isalnum())


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
