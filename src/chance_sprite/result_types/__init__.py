# chance_sprite/result_types/__init__.py
from __future__ import annotations

import random
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .additive_result import AdditiveResult as AdditiveResult
    from .break_limit_result import BreakTheLimitHitsResult as BreakTheLimitHitsResult
    from .close_call_result import CloseCallResult as CloseCallResult
    from .hits_result import HitsResult as HitsResult
    from .push_limit_result import PushTheLimitHitsResult as PushTheLimitHitsResult
    from .second_chance_result import SecondChanceHitsResult as SecondChanceHitsResult

_default_random = random.Random()


class Glitch(Enum):
    NONE = "none"
    GLITCH = "glitch"
    CRITICAL = "critical"
