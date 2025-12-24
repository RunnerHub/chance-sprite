# file_sprite.py
from __future__ import annotations

import json
import os
from pathlib import Path

from platformdirs import PlatformDirs

from . import APP_NAME

class CacheFile:
    _cache_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_cache_dir)
    def __init__(self, filename: str):
        self.path = self._cache_dir / filename
        self.data = self._load()
    
    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                v = json.load(f)
            return v if isinstance(v, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

class ConfigFile:
    _config_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_config_dir)
    def __init__(self, filename: str):
        self.path = self._config_dir / filename
        self.data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                v = json.load(f)
            return v if isinstance(v, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def get(self, key, default=None):
        return self.data.get(key, default)

class StateFile:
    _state_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_state_dir)
    def __init__(self, filename: str):
        self.path = self._state_dir / filename
        self.data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                v = json.load(f)
            return v if isinstance(v, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()
