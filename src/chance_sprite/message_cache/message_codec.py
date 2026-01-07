from __future__ import annotations

import importlib
import pkgutil
import sys
from dataclasses import is_dataclass, fields
from types import ModuleType
from typing import Any, get_origin, get_args, get_type_hints


class MessageCodec:
    def __init__(self):
        self.registry = {}
        self._hint_cache: dict[type, dict[str, Any]] = {}

    def build_registry_default(self):
        from .. import result_types, roll_types, message_cache, rollui, emojis
        self.build_registry([result_types, roll_types, message_cache, rollui, emojis])

    def build_registry(self, packages: list[ModuleType]):
        for pkg in packages:
            for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
                if m.ispkg:
                    continue
                leaf = m.name.rsplit(".", 1)[-1]
                if leaf.startswith("_"):
                    continue

                mod = importlib.import_module(m.name)

                for obj in vars(mod).values():
                    if isinstance(obj, type) and is_dataclass(obj):
                        tag = getattr(obj, "__tag__", obj.__name__)  # allow override
                        self.registry[tag] = obj

    def register(self, tag: str):
        def deco(cls: type):
            self.registry[tag] = cls
            setattr(cls, "__tag__", tag)
            return cls
        return deco

    def alias(self, tag: str):
        def deco(cls: type):
            self.registry[tag] = cls
            return cls
        return deco

    def decode_with_hint(self, value, hint):
        # If it's a tagged dict, dispatch regardless of hint
        if isinstance(value, dict) and "type" in value:
            return self.dataclass_from_dict(value)

        # Recurse containers
        if isinstance(value, list):
            # try to use list[T] hint if present
            if get_origin(hint) is list:
                (item_t,) = get_args(hint) or (Any,)
                return [self.decode_with_hint(x, item_t) for x in value]
            return [self.decode_with_hint(x, Any) for x in value]

        if isinstance(value, dict):
            # If we have dict[K, V] type info, use it
            if get_origin(hint) is dict:
                key_t, val_t = get_args(hint) or (Any, Any)

                def coerce_key(k: Any) -> Any:
                    if key_t is int and isinstance(k, str):
                        # only convert clean integer strings; otherwise keep as-is
                        # (prevents blowing up on keys like "123abc")
                        try:
                            return int(k)
                        except ValueError:
                            return k
                    return k

                return {
                    coerce_key(k): self.decode_with_hint(val, val_t)
                    for k, val in value.items()
                }

            # No hint: do NOT coerce keys; just recurse values
            return {k: self.decode_with_hint(val, Any) for k, val in value.items()}

        return value

    def dataclass_from_dict(self, obj: Any) -> Any:
        # Don't guess at objects without type parameters
        if not (isinstance(obj, dict) and "type" in obj):
            return obj

        tag = obj.get("type")
        if not isinstance(tag, str):
            raise ValueError("type must be a string")

        cls = self.registry.get(tag)
        if cls is None:
            raise ValueError(f"Unknown type tag: {tag}")

        # Resolve postponed annotations (and forward refs) to real types
        type_hints = self._hint_cache.get(cls)
        if type_hints is None:
            globalns = vars(sys.modules[cls.__module__])
            localns = dict(vars(cls))  # Class locals + type parameters (PEP 695)
            type_params = getattr(cls, "__type_params__", ())
            for tp in type_params:
                # tp is a TypeVar-like object with a __name__
                localns[getattr(tp, "__name__", str(tp))] = tp
            type_hints = get_type_hints(cls, globalns=globalns, localns=localns)
            self._hint_cache[cls] = type_hints

        kwargs = {}
        for f in fields(cls):
            if f.name in obj:
                hint = type_hints.get(f.name, Any)
                kwargs[f.name] = self.decode_with_hint(obj[f.name], hint)
        return cls(**kwargs)

    def dict_from_dataclass(self, obj: Any) -> Any:
        if is_dataclass(obj):
            type_tag = getattr(obj.__class__, "__tag__", obj.__class__.__name__)
            out = {"type": type_tag}
            for f in fields(obj):
                out[f.name] = self.dict_from_dataclass(getattr(obj, f.name))
            return out
        if isinstance(obj, list):
            return [self.dict_from_dataclass(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.dict_from_dataclass(v) for k, v in obj.items()}
        return obj
