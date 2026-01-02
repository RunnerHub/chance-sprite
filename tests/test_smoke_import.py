import importlib
import pkgutil

SKIP_PREFIXES = (
    "chance_sprite.__main__",
)


def iter_all_modules(root_pkg: str):
    pkg = importlib.import_module(root_pkg)
    yield pkg.__name__

    if not hasattr(pkg, "__path__"):
        return

    for mod in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        yield mod.name


def test_all_modules_import():
    for mod in iter_all_modules("chance_sprite"):
        if any(mod.startswith(p) for p in SKIP_PREFIXES):
            continue
        importlib.import_module(mod)
