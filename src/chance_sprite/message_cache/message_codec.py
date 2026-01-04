from __future__ import annotations

import importlib
import pkgutil
from dataclasses import is_dataclass, fields
from types import ModuleType
from typing import Any, get_origin, get_args, get_type_hints


class MessageCodec:
    def __init__(self):
        self.registry = {}
        self._hint_cache: dict[type, dict[str, Any]] = {}  # type: ignore[annotation-unchecked]

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

    def _decode_value(self, v, hint):
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
                    coerce_key(k): self._decode_value(val, val_t)
                    for k, val in v.items()
                }

            # No hint: do NOT coerce keys; just recurse values
            return {k: self._decode_value(val, Any) for k, val in v.items()}

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

        # Resolve postponed annotations (and forward refs) to real types
        type_hints = self._hint_cache.get(cls)
        if type_hints is None:
            try:
                type_hints = get_type_hints(cls)
            except NameError:
                type_hints = getattr(cls, "__annotations__", {})
            self._hint_cache[cls] = type_hints

        kwargs = {}
        for f in fields(cls):
            if f.name in obj:
                hint = type_hints.get(f.name, Any)
                kwargs[f.name] = self._decode_value(obj[f.name], hint)
        return cls(**kwargs)

    def encode(self, obj: Any) -> Any:
        tag = getattr(obj.__class__, "__tag__", obj.__class__.__name__)
        if is_dataclass(obj):
            out = {"type": tag}
            for f in fields(obj):
                out[f.name] = self.encode(getattr(obj, f.name))
            return out
        if isinstance(obj, list):
            return [self.encode(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.encode(v) for k, v in obj.items()}
        return obj
