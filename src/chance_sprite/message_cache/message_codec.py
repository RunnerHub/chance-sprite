from __future__ import annotations

import importlib
import pkgutil
from dataclasses import is_dataclass, fields
from types import ModuleType
from typing import Any, get_origin, get_args


class MessageCodec:
    def __init__(self):
        self.registry = {}

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

    def _decode_value(self, v: Any, hint: Any) -> Any:
        # If it's a tagged dict, dispatch regardless of hint
        if isinstance(v, dict) and "type" in v:
            return self.decode(v)

        # Recurse containers
        if isinstance(v, list):
            # try to use list[T] hint if present
            if get_origin(hint) is list:
                (item_t,) = get_args(hint) or (Any,)
                return [self._decode_value(x, item_t) for x in v]
            return [self.decode(x) if isinstance(x, dict) else x for x in v]

        if isinstance(v, dict):
            return {k: self.decode(val) if isinstance(val, dict) else val for k, val in v.items()}

        return v

    def decode(self, obj: Any) -> Any:
        if not (isinstance(obj, dict) and "type" in obj):
            return obj

        tag = obj.get("type")
        if not isinstance(tag, str):
            raise ValueError("type must be a string")

        cls = self.registry.get(tag)
        if cls is None:
            raise ValueError(f"Unknown type tag: {tag}")

        kwargs = {}
        for f in fields(cls):
            if f.name in obj:
                kwargs[f.name] = self._decode_value(obj[f.name], f.type)
        return cls(**kwargs)

    def encode(self, obj: Any) -> Any:
        if is_dataclass(obj):
            out = {"type": obj.__class__.__name__}
            for f in fields(obj):
                out[f.name] = self.encode(getattr(obj, f.name))
            return out
        if isinstance(obj, list):
            return [self.encode(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.encode(v) for k, v in obj.items()}
        return obj
