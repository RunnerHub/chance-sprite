# common.py
from __future__ import annotations

import logging
import random
from enum import Enum

log = logging.getLogger(__name__)

_default_random = random.Random()


class Glitch(Enum):
    NONE = "none"
    GLITCH = "glitch"
    CRITICAL = "critical"

MAX_EMOJI_DICE = 120  # Guard against content limit (~27 characters per emoji, 4096 characters max)
# TODO: per-post limit instead of per-roll


