from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Iterable

# Add all modules in package to importable from package
__all__ = []

for info in pkgutil.iter_modules(__path__):
    # Try importing
    module = importlib.import_module(f"{__name__}.{info.name}")

    # Iterate through the module's namespace
    for name, obj in vars(module).items():
        # Ignore private members
        if name.startswith("_"):
            continue

        # Only export things defined in this module
        if getattr(obj, "__module__", None) == module.__name__:
            globals()[name] = obj
            __all__.append(name)


def discover_modules() -> Iterable[ModuleType]:
    """Import every non-private module in this package and yield it."""
    pkg = __name__
    for m in pkgutil.walk_packages(__path__):
        if m.ispkg:
            continue
        if m.name.startswith("_"):
            continue
        yield importlib.import_module(f"{pkg}.{m.name}")
