# fungen.py
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Coroutine,
    Mapping,
    get_args,
    get_origin,
    Annotated,
    get_type_hints,
)

import discord
from discord import app_commands
from makefun import with_signature

from chance_sprite.sprite_context import InteractionContext

RollFunc = Callable[..., Any]


@dataclass(frozen=True)
class Desc:
    text: str


@dataclass(frozen=True)
class RollMeta:
    group: str | None = None  # one level deep
    name: str | None = None
    desc: str | None = None


@dataclass(frozen=True)
class Choices:
    values: tuple[app_commands.Choice[Any], ...]


def extract_choices(metadata: list[Any]) -> tuple[app_commands.Choice[Any], ...] | None:
    for m in metadata:
        if isinstance(m, Choices):
            return m.values
    return None


# decorator to indicate a command that should be
def roll_command(
    *, group: str | None = None, name: str | None = None, desc: str | None = None
):
    meta = RollMeta(group=group, name=name, desc=desc)

    def deco(fn: RollFunc) -> RollFunc:
        setattr(fn, "__roll_meta__", meta)
        return fn

    return deco


def split_annotated(annotation: Any) -> tuple[Any, list[Any]]:
    if get_origin(annotation) is Annotated:
        args = list(get_args(annotation))
        return args[0], args[1:]
    return annotation, []


def extract_desc(metadata: list[Any], param_name: str) -> str:
    for m in metadata:
        if isinstance(m, Desc):
            return m.text
    raise ValueError(f"Missing Desc(...) for parameter '{param_name}'")


def build_discord_callback(
    *,
    roll_func: RollFunc,
    invoke: Callable[[discord.Interaction, Mapping[str, Any]], Coroutine[Any, Any, None]],
) -> Callable[..., Coroutine[Any, Any, None]]:
    qualified_name = f"{roll_func.__module__}.{roll_func.__qualname__}"

    signature = inspect.signature(roll_func)

    type_hints = get_type_hints(roll_func, include_extras=True)

    params: list[dict[str, Any]] = [
        {
            "name": "label",
            "annotation": str,
            "description": "A label to describe the roll.",
            "default": ...,
        }
    ]

    for p in signature.parameters.values():
        if p.name in ("self", "cls"):
            continue
        try:
            hinted_annotations = type_hints.get(p.name, p.annotation)
            base_ann, meta = split_annotated(hinted_annotations)
            desc = extract_desc(meta, p.name)  # <- can raise
        except Exception as exc:
            raise ValueError(
                f"{qualified_name}: invalid parameter {p.name!r}: {exc}"
            ) from exc
        default = p.default if p.default is not inspect._empty else ...
        choices = extract_choices(meta)
        params.append(
            {
                "name": p.name,
                "annotation": base_ann,  # already Range[...] / bool / etc
                "description": desc,
                "default": default,
                "choices": choices,
            }
        )

    signature_parts = ["interaction"]
    annotation_dict: dict[str, Any] = {"interaction": discord.Interaction}
    defaults: dict[str, Any] = {}
    choices_by_param: dict[str, list[app_commands.Choice[Any]]] = {}

    for p in params:
        pname = p["name"]
        annotation_dict[pname] = p["annotation"]
        ch = p.get("choices")
        if ch:
            choices_by_param[p["name"]] = list(ch)
        if p["default"] is ...:
            signature_parts.append(pname)
        else:
            default_value = p["default"]
            if default_value is None or isinstance(
                default_value, (int, float, bool, str)
            ):
                signature_parts.append(f"{pname}={default_value!r}")
            else:
                signature_parts.append(f"{pname}={pname}_default")
                defaults[f"{pname}_default"] = default_value

    signature_text = f"({', '.join(signature_parts)})"
    param_names = ["interaction"] + [p["name"] for p in params]

    async def implementation(*args, **kwargs):
        bound = dict(kwargs)
        for k, v in zip(param_names, args):
            bound.setdefault(k, v)
        interaction = bound.pop("interaction")
        await invoke(interaction, bound)

    callback = with_signature(signature_text, evaldict=defaults)(implementation)
    callback.__annotations__ = annotation_dict

    callback = app_commands.describe(**{p["name"]: p["description"] for p in params})(
        callback
    )
    if choices_by_param:
        callback = app_commands.choices(**choices_by_param)(callback)
    return callback


async def invoke_roll_and_transmit(
    interaction: discord.Interaction,
    *,
    roll_func: RollFunc,
    raw_args: Mapping[str, Any],
) -> None:
    roll_kwargs = dict(raw_args)
    label = roll_kwargs.pop("label", "")
    try:
        result = roll_func(**roll_kwargs)
    except TypeError as exc:
        await interaction.response.send_message(
            f"Internal command mapping error: {exc}", ephemeral=True
        )
        return
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    await InteractionContext(interaction).transmit_result(label=label, result=result)
