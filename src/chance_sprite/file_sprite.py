from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from collections.abc import Mapping, MutableMapping, Iterator
from typing import Any

from platformdirs import PlatformDirs

from . import APP_NAME

log = logging.getLogger(__name__)

class ReadableFile(Mapping[str, Any]):
    def __init__(self, _dir: Path, filename: str):
        self._dir = _dir
        self.path = _dir / filename
        self.data: dict[str, Any] = self._load()

    # File I/O (read-only)
    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            log.warning("File not found: %s; proceeding without it", self.path)
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                v = json.load(f)
            if isinstance(v, dict):
                return v
            log.warning(
                "Expected JSON object in %s, got %s; using empty data",
                self.path,
                type(v).__name__,
            )
            return {}
        except json.JSONDecodeError:
            log.exception("Invalid JSON in %s; using empty data", self.path)
            return {}
        except OSError:
            log.exception("Could not read %s; using empty data", self.path)
            return {}

    # Collection methods (read-only)
    def __getitem__(self, key: str) -> Any:
        return self.data[key]  # raises KeyError if missing

    def __iter__(self) -> Iterator[str]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)


class WriteableFile(ReadableFile, MutableMapping[str, Any]):
    # File I/O (write)
    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.path)

    # Collection methods (write-through)
    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def __delitem__(self, key: str) -> None:
        del self.data[key]  # raises KeyError if missing
        self.save()

    # Helpers
    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def remove(self, key: str) -> None:
        self.data.pop(key, None)
        self.save()


class CacheFile(WriteableFile):
    _cache_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_cache_dir)
    def __init__(self, filename: str):
        super().__init__(self._cache_dir, filename)

class ConfigFile(ReadableFile):
    _config_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_config_dir)
    def __init__(self, filename: str):
        super().__init__(self._config_dir, filename)

class StateFile(WriteableFile):
    _state_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_state_dir)
    def __init__(self, filename: str):
        super().__init__(self._state_dir, filename)