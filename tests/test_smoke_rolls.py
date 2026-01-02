from __future__ import annotations

import importlib

# First we smoke test just importing them.
ROLL_MODULES: list[str] = [
    "chance_sprite.common.common",
    "chance_sprite.common.commonui",
    "chance_sprite.roll_types.bind",
    "chance_sprite.roll_types.extended",
    "chance_sprite.roll_types.opposed",
    "chance_sprite.roll_types.simple",
    "chance_sprite.roll_types.spell",
    "chance_sprite.roll_types.startingcash",
    "chance_sprite.roll_types.summon",
    "chance_sprite.roll_types.threshold",
]


def test_import_roll_modules() -> None:
    # Import errors are crashes too.
    for mod in ROLL_MODULES:
        importlib.import_module(mod)