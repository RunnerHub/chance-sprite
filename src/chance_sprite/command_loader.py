# rolld6_commands.py
from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from types import ModuleType
from typing import Callable

from discord import app_commands

from chance_sprite.fungen import (
    RollMeta,
    build_discord_callback,
    invoke_roll_and_transmit,
)
from chance_sprite.sprite_context import ClientContext

log = logging.getLogger(__name__)
RollFunc = Callable[..., object]


def iter_modules(package_name: str) -> list[ModuleType]:
    pkg = importlib.import_module(package_name)
    if not hasattr(pkg, "__path__"):
        raise ValueError(f"{package_name} is not a package")
    return [
        importlib.import_module(m.name)
        for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + ".")
    ]


def is_roll_command(obj: object) -> bool:
    return inspect.isfunction(obj) and hasattr(obj, "__roll_meta__")


def find_roll_commands(package_name: str) -> list[RollFunc]:
    fns: list[RollFunc] = []
    for mod in iter_modules(package_name):
        for _, obj in inspect.getmembers(mod, is_roll_command):
            fns.append(obj)  # type: ignore[arg-type]
    return fns


def derive_group_from_module(mod: str, base: str) -> str | None:
    if mod == base:
        return None
    if not mod.startswith(base + "."):
        return None
    rest = mod[len(base) + 1 :]
    return rest.split(".", 1)[0] if rest else None


def identity(fn: RollFunc, base_package: str) -> tuple[str | None, str, str]:
    meta: RollMeta | None = getattr(fn, "__roll_meta__", None)
    group = (
        meta.group
        if meta and meta.group is not None
        else derive_group_from_module(fn.__module__, base_package)
    )
    name = meta.name if meta and meta.name else fn.__name__.removeprefix("roll_")
    desc = meta.desc if meta and meta.desc else (inspect.getdoc(fn) or "Roll command.")
    return group, name, desc


async def setup(bot: ClientContext) -> None:
    root = app_commands.Group(
        name=bot.base_command_name, description="SR5 d6 dice rolling tools."
    )
    app_commands.allowed_installs(guilds=True, users=True)(root)
    app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)(root)

    base_package = "chance_sprite.roll_types"
    roll_funcs = find_roll_commands(base_package)

    subgroups: dict[str, app_commands.Group] = {}
    seen: set[tuple[str | None, str]] = set()

    for fn in roll_funcs:
        group_name, cmd_name, cmd_desc = identity(fn, base_package)

        key = (group_name, cmd_name)
        if key in seen:
            raise RuntimeError(
                f"Duplicate command: group={group_name!r} name={cmd_name!r} from {fn.__module__}.{fn.__name__}"
            )
        seen.add(key)

        async def _invoke(interaction, args, _fn=fn):
            await invoke_roll_and_transmit(interaction, roll_func=_fn, raw_args=args)

        callback = build_discord_callback(roll_func=fn, invoke=_invoke)
        cmd = app_commands.Command(
            name=cmd_name, description=cmd_desc, callback=callback
        )

        if group_name is None:
            root.add_command(cmd)
        else:
            g = subgroups.get(group_name)
            if g is None:
                g = app_commands.Group(
                    name=group_name, description=f"{group_name.title()} commands"
                )
                root.add_command(g)
                subgroups[group_name] = g
            g.add_command(cmd)

    bot.tree.add_command(root)
    log.info(
        "Registered /%s with %d roll command(s) across %d subgroup(s)",
        root.name,
        len(roll_funcs),
        len(subgroups),
    )
