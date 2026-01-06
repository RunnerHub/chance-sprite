# Add all modules in package to importable from package
from __future__ import annotations

import importlib
import pkgutil

__all__ = []

from chance_sprite.message_cache.message_codec import MessageCodec

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

message_codec = MessageCodec()
