# chance_sprite/result_types/__init__.py
from __future__ import annotations

import importlib
import pkgutil
import random
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .additive_result import AdditiveResult
    from .break_limit_result import BreakTheLimitHitsResult
    from .close_call_result import CloseCallResult
    from .hits_result import HitsResult
    from .push_limit_result import PushTheLimitHitsResult
    from .second_chance_result import SecondChanceHitsResult

_default_random = random.Random()


class Glitch(Enum):
    NONE = "none"
    GLITCH = "glitch"
    CRITICAL = "critical"


# Add all modules in package to importable from package
__all__ = []

for info in pkgutil.iter_modules(__path__):
    # Try importing
    module = importlib.import_module(f"{__name__}.{info.name}")

    # Iterate through the module's namespace
    for name, obj in vars(module).items():
        # Ignore private members
        if name.startswith("_"):
            continue

        # Only export things defined in that module
        if getattr(obj, "__module__", None) == module.__name__:
            globals()[name] = obj
            __all__.append(name)
