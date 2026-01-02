# Add all modules in package to importable from package
__all__ = []

import importlib
import pkgutil

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
