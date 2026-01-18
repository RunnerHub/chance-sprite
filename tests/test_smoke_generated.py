from __future__ import annotations

import importlib
import inspect
import pkgutil
import types
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Union, cast, get_args, get_origin, get_type_hints

import pytest
from discord import app_commands
from discord.app_commands.transformers import RangeTransformer

from chance_sprite.discord_sprite import DiscordSprite
from chance_sprite.emojis.emoji_manager import RAW_TEXT_EMOJI_PACK, EmojiManager

# Import these from your real generator module
from chance_sprite.fungen import Choices, Desc
from chance_sprite.sprite_context import InteractionContext  # adjust names if different

PACKAGE = "chance_sprite.roll_types"


def iter_roll_modules() -> list[str]:
    pkg = importlib.import_module(PACKAGE)
    out: list[str] = []
    for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        leaf = m.name.rsplit(".", 1)[-1]
        if leaf.startswith("_"):
            continue
        out.append(m.name)
    return out


def find_roll_commands(mod) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for name, obj in vars(mod).items():
        if not inspect.isfunction(obj):
            continue
        if not hasattr(obj, "__roll_meta__"):
            continue
        out.append((f"{mod.__name__}.{name}", obj))
    return out


def split_annotated(tp: Any) -> tuple[Any, list[Any]]:
    if get_origin(tp) is Annotated:
        args = list(get_args(tp))
        return args[0], args[1:]
    return tp, []


def has_desc(tp: Any) -> bool:
    base, meta = split_annotated(tp)
    return any(isinstance(m, Desc) for m in meta)


def is_optional(tp: Any) -> tuple[bool, Any]:
    origin = get_origin(tp)
    if origin not in (Union, types.UnionType):
        return False, tp
    args = get_args(tp)
    if len(args) != 2 or type(None) not in args:
        return False, tp
    inner = args[0] if args[1] is type(None) else args[1]
    return True, inner


def default_for_type(tp: Any, *, none_ok: bool) -> Any:
    # unwrap Annotated
    tp, _meta = split_annotated(tp)

    # If the param has explicit choices, pick the first valid choice value.
    for m in _meta:
        if isinstance(m, Choices):
            return m.values[0].value

    # Optional[T]
    opt, inner = is_optional(tp)
    if opt and none_ok:
        return None
    if opt:
        tp = inner

    # app_commands.Range[int, lo, hi] etc: treat like its underlying type
    if get_origin(tp) is app_commands.Range:
        args = get_args(tp)
        # args[0] is the underlying type, usually int
        tp = args[0]

    origin = get_origin(tp)
    if origin is not None:
        raise TypeError(f"Unsupported generic type: {tp!r}")

    if tp is int:
        return 0 if none_ok else 6
    if tp is float:
        return 1.0
    if tp is bool:
        return False
    if tp is str:
        return "" if none_ok else "smoke"
    if isinstance(tp, RangeTransformer):
        base = _range_transformer_base(tp)
        if base is float:
            return 1.0
        return 0 if none_ok else 6
    if inspect.isclass(tp) and issubclass(tp, Enum):
        return next(iter(tp))

    raise TypeError(f"Unsupported type: {tp!r}")


def _range_transformer_base(tp: RangeTransformer) -> type:
    # discord.py internals vary; try a few likely attrs
    for attr in ("annotation", "_annotation", "inner", "_inner"):
        v = getattr(tp, attr, None)
        if v in (int, float):
            return v
    return int


def build_kwargs(fn: Any, *, none_ok: bool) -> dict[str, Any]:
    sig = inspect.signature(fn)
    hints = get_type_hints(fn, include_extras=True)

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
    fn: Any
    none_ok: bool


def collect_cases() -> list[Case]:
    cases: list[Case] = []
    for modname in iter_roll_modules():
        mod = importlib.import_module(modname)
        for qualname, fn in find_roll_commands(mod):
            cases.append(Case(qualname=qualname, fn=fn, none_ok=True))
            cases.append(Case(qualname=qualname, fn=fn, none_ok=False))
    return cases


_CASES = collect_cases()


def test_smoke_collected_something() -> None:
    assert _CASES, f"Collected 0 @roll_command functions from {PACKAGE}"


def test_all_roll_commands_have_kw_only_and_desc() -> None:
    # Fast static validation: catches mistakes before runtime smoke
    for case in _CASES[::2]:  # only one per function (skip the duplicated none_ok)
        fn = case.fn
        sig = inspect.signature(fn)

        # kw-only enforcement
        bad = [
            p.name
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        assert not bad, f"{case.qualname} has non-kw-only params: {bad}"

        # Desc enforcement: require Desc on every param except maybe internal ones
        hints = get_type_hints(fn, include_extras=True)
        for pname, p in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            ann = hints.get(pname, None)
            assert ann is not None, f"{case.qualname} missing annotation for {pname!r}"
            assert has_desc(ann), (
                f"{case.qualname} param {pname!r} missing Desc(...) metadata"
            )


class FakeAvatar:
    def __init__(self) -> None:
        self.url = ""


class FakeUser:
    def __init__(self) -> None:
        self.display_name = ""
        self.display_avatar = FakeAvatar()
        self.id = 0

class FakeMessage:
    def __init__(self) -> None:
        self.id = 0

class FakeInteraction:
    def __init__(self) -> None:
        self.user = FakeUser()
        self.guild_id = 0
        self.message = FakeMessage()

class FakeAvatarStore:
    def __init__(self) -> None:
        pass

    def get_avatar(self, a, b):
        return ("", "")
        

class FakeClient:
    def __init__(self) -> None:
        self.message_store = dict()
        self.webhook_handles = dict()
        self.user_avatar_store = FakeAvatarStore()

class FakeContext(InteractionContext):
    def __init__(self) -> None:
        self.emoji_manager = EmojiManager("chance_sprite.emojis")
        # minimal setup
        self.emoji_manager.packs = RAW_TEXT_EMOJI_PACK
        self.message_handles = {}  # if your code touches it
        self.base_command_name = None
        self.interaction = FakeInteraction()
        self.client = FakeClient()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _CASES,
    ids=lambda c: f"{c.qualname}|{'none' if c.none_ok else 'filled'}",
)
async def test_roll_smoke_per_item(case: Case) -> None:
    kwargs = build_kwargs(case.fn, none_ok=case.none_ok)

    try:
        roll = case.fn(**kwargs)
    except ValueError:
        # If you validate inputs and reject dummy values, that’s fine.
        # But it should reject predictably, not crash.
        return

    if hasattr(roll, "build_view"):
        context_obj = cast(object, FakeContext())
        context = cast(DiscordSprite, context_obj)
        roll.build_view("Smoke", context)
