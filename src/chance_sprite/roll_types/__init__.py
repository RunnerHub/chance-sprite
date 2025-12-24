from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Iterable

def discover_modules() -> Iterable[ModuleType]:
    """Import every non-private module in this package and yield it."""
    pkg = __name__
    for m in pkgutil.iter_modules(__path__):
        if m.ispkg:
            continue
        if m.name.startswith("_"):
            continue
        yield importlib.import_module(f"{pkg}.{m.name}")