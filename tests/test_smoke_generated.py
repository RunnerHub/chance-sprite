from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from dataclasses import is_dataclass
from enum import Enum
from typing import Any, get_args, get_origin, get_type_hints, cast

import pytest

from chance_sprite.emojis.emoji_manager import EmojiPack, EmojiManager, RAW_TEXT_EMOJI_PACK
from chance_sprite.file_sprite import RollRecordCacheFile
from chance_sprite.sprite_context import ClientContext

PACKAGE = "chance_sprite.roll_types"


def iter_roll_modules() -> list[str]:
    pkg = importlib.import_module(PACKAGE)
    out: list[str] = []
    for m in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        leaf = m.name.rsplit(".", 1)[-1]
        if leaf.startswith("_"):
            continue
        out.append(m.name)
    return out


def find_roll_callables(mod) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for _, obj in vars(mod).items():
        if not inspect.isclass(obj):
            continue
        if not is_dataclass(obj):
            continue
        roll = getattr(obj, "roll", None)
        if callable(roll):
            out.append((f"{mod.__name__}.{obj.__name__}.roll", roll))
    return out


def is_optional(tp: Any) -> tuple[bool, Any]:
    origin = get_origin(tp)
    if origin is None:
        return False, tp
    args = get_args(tp)
    if len(args) == 2 and type(None) in args:
        inner = args[0] if args[1] is type(None) else args[1]
        return True, inner
    return False, tp


def default_for_type(tp: Any, *, none_ok: bool) -> Any:
    opt, inner = is_optional(tp)
    if opt and none_ok:
        return None
    if opt:
        tp = inner

    origin = get_origin(tp)
    if origin is not None:
        raise TypeError(f"Unsupported generic type: {tp!r}")

    if tp is int:
        if none_ok:
            return 0
        else:
            return 6
    if tp is float:
        return 1.0
    if tp is bool:
        return False
    if tp is str:
        if none_ok:
            return ""
        else:
            return "smoke"
    if inspect.isclass(tp) and issubclass(tp, Enum):
        return next(iter(tp))

    raise TypeError(f"Unsupported type: {tp!r}")


def build_kwargs(fn: Any, *, none_ok: bool) -> dict[str, Any]:
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)

    kwargs: dict[str, Any] = {}
    for name, p in sig.parameters.items():
        if name in ("cls", "self"):
            continue
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        if p.default is not inspect._empty:
            continue  # rely on fn default
        ann = hints.get(name, Any)
        kwargs[name] = default_for_type(ann, none_ok=none_ok)
    return kwargs

@dataclass(frozen=True)
class Case:
    qualname: str
    roll_fn: Any
    none_ok: bool

def collect_cases() -> list[Case]:
    cases: list[Case] = []
    for modname in iter_roll_modules():
        mod = importlib.import_module(modname)
        for qualname, roll_fn in find_roll_callables(mod):
            cases.append(Case(qualname=qualname, roll_fn=roll_fn, none_ok=True))
            cases.append(Case(qualname=qualname, roll_fn=roll_fn, none_ok=False))
    return cases

_CASES = collect_cases()


def test_smoke_collected_something() -> None:
    # This answers your "am I sure it's collecting correctly?"
    assert _CASES, f"Collected 0 roll() callables from {PACKAGE}"


D6_EMOJIS = [
    "<:d6r1:1447759071745937438>",
    "<:d6r2:1447759070420537456>",
    "<:d6r3:1447759069124497492>",
    "<:d6r4:1447759074954444812>",
    "<:d6r5:1447759074119778396>",
    "<:d6r6:1447759073096368149>",
]
emoji_packs = EmojiPack(D6_EMOJIS, D6_EMOJIS, D6_EMOJIS, ("", "glitch", "critical glitch"))


class FakeContext:
    def __init__(self) -> None:
        self.emoji_manager = EmojiManager("chance_sprite.emojis")
        self.emoji_manager.by_name["alchemy"] = "asdf"
        self.emoji_manager.packs = RAW_TEXT_EMOJI_PACK
        self.message_cache = RollRecordCacheFile("message_cache.json")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _CASES,
    ids=lambda c: f"{c.qualname}|{'none' if c.none_ok else 'filled'}",
)
async def test_roll_smoke_per_item(case: Case) -> None:
    kwargs = build_kwargs(case.roll_fn, none_ok=case.none_ok)
    roll = case.roll_fn(**kwargs)

    if hasattr(roll, "build_view"):
        builder = roll.build_view("Smoke")
        # noinspection PyInvalidCast
        ctx = cast(ClientContext, FakeContext())
        builder(ctx)
