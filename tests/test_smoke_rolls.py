from __future__ import annotations

import importlib
from typing import Callable

from chance_sprite.roll_types.threshold import ThresholdResult

# First we smoke test just importing them.
ROLL_MODULES: list[str] = [
    "chance_sprite.roll_types.common",
    "chance_sprite.roll_types.threshold",
    "chance_sprite.roll_types.opposed",
    "chance_sprite.roll_types.extended",
    "chance_sprite.roll_types.summon",
    "chance_sprite.roll_types.bind",
    "chance_sprite.roll_types.spell",
    "chance_sprite.roll_types.startingcash",
]


def test_import_roll_modules() -> None:
    # Import errors are crashes too.
    for mod in ROLL_MODULES:
        importlib.import_module(mod)