from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, MutableMapping, Iterator
from pathlib import Path
from typing import Any

from platformdirs import PlatformDirs

from . import APP_NAME
from .message_cache.message_codec import MessageCodec
from .message_cache.roll_record import MessageRecord

log = logging.getLogger(__name__)


class ReadableFile[K, V](Mapping[K, V]):
    def __init__(self, _dir: Path, filename: str):
        self._dir = _dir
        self.path = _dir / filename
        self.data: dict[K, V] = self._load()

    # File I/O (read-only)
    def _load(self) -> dict[K, V]:
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
    def __getitem__(self, key: K) -> Any:
        return self.data[key]  # raises KeyError if missing

    def __iter__(self) -> Iterator[K]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)


class WriteableFile[K, V](ReadableFile, MutableMapping[K, V]):
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
    def __setitem__(self, key: K, value: Any) -> None:
        self.data[key] = value
        self.save()

    def __delitem__(self, key: K) -> None:
        del self.data[key]  # raises KeyError if missing
        self.save()

    # Helpers
    def set(self, key: K, value: Any) -> None:
        self.data[key] = value
        self.save()

    def remove(self, key: K) -> None:
        self.data.pop(key, None)
        self.save()


class CacheFile[K, V](WriteableFile[K, V]):
    _cache_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_cache_dir)
    def __init__(self, filename: str):
        super().__init__(self._cache_dir, filename)


class ConfigFile[K, V](ReadableFile[K, V]):
    _config_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_config_dir)
    def __init__(self, filename: str):
        super().__init__(self._config_dir, filename)


class StateFile[K, V](WriteableFile[K, V]):
    _state_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_state_dir)
    def __init__(self, filename: str):
        super().__init__(self._state_dir, filename)


class RollRecordCacheFile(CacheFile[int, MessageRecord]):
    def __init__(self, filename: str):
        self.message_codec = MessageCodec()
        import chance_sprite.result_types as result_types
        import chance_sprite.roll_types as roll_types
        import chance_sprite.message_cache as message_cache
        self.message_codec.build_registry([result_types, roll_types, message_cache])
        super().__init__(filename)

    def _load(self) -> dict[int, MessageRecord]:
        data = super()._load()
        restored = self.message_codec.decode(data)
        return restored

    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        encoded_data = self.message_codec.encode(self.data)
        log.info(encoded_data)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(encoded_data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.path)
        log.info("File saved!")

    def put(self, msg: MessageRecord) -> None:
        self.set(msg.message_id, msg)
