from __future__ import annotations

import json
import logging
import os
import sqlite3
from collections.abc import Mapping, MutableMapping, Iterator
from pathlib import Path
from typing import Any, Optional

import msgspec
from platformdirs import PlatformDirs

from . import APP_NAME
from .message_cache import message_codec
from .message_cache.message_record import MessageRecord

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


class DatabaseHandle:
    _state_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_state_dir)

    def __init__(self, filename: str):
        self.path = self._state_dir / filename
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.path, isolation_level=None)  # autocommit
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=FULL;")

    def init_table_intkey(self, table_name: str):
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
              record_id INTEGER PRIMARY KEY,
              payload BLOB NOT NULL
            )
        """, )

    def close(self) -> None:
        self.conn.close()

    def get(self, table: str, record_id: int) -> Optional[dict]:
        row = self.conn.execute(
            f"SELECT payload FROM {table} WHERE record_id=?",
            (record_id,),
        ).fetchone()
        if row is None:
            return None

        return msgspec.msgpack.decode(row[0])

    def put(self, table: str, record_id: int, data_dict: dict) -> None:
        payload_bytes: bytes = msgspec.msgpack.encode(data_dict)

        self.conn.execute(
            f"INSERT INTO {table}(record_id, payload) VALUES(?, ?) "
            "ON CONFLICT(record_id) DO UPDATE SET payload=excluded.payload",
            (record_id, payload_bytes),
        )

    def seed(self, table: str, record_id: int, data_dict: dict):
        payload_bytes: bytes = msgspec.msgpack.encode(data_dict)
        self.conn.execute(
            f"INSERT INTO {table}(record_id, payload) VALUES(?, ?) "
            "ON CONFLICT(record_id) DO NOTHING",
            (record_id, payload_bytes),
        )

    def delete(self, table: str, record_id: int) -> None:
        self.conn.execute(f"DELETE FROM {table} WHERE record_id=?", (record_id,))

    def count(self, table: str) -> int:
        (n,) = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(n)

    def iter_ids(self, table: str) -> Iterator[int]:
        cur = self.conn.execute(f"SELECT record_id FROM {table} ORDER BY record_id")
        for (rid,) in cur:
            yield int(rid)


class DatabaseTableInt[V](MutableMapping[int, V]):
    def __init__(self, database: DatabaseHandle, table_name: str):
        super().__init__()
        database.init_table_intkey(table_name)
        self.database = database
        self.table = table_name

    def get_optional(self, record_id: int) -> Optional[V]:
        encoded = self.database.get(self.table, record_id)
        return message_codec.dataclass_from_dict(encoded)

    def set(self, record_id: int, obj: V) -> None:
        encoded = message_codec.dict_from_dataclass(obj)
        self.database.put(self.table, record_id, encoded)

    def seed(self, record_id: int, obj: V):
        encoded = message_codec.dict_from_dataclass(obj)
        self.database.seed(self.table, record_id, encoded)

    def delete(self, record_id: int) -> None:
        self.database.delete(self.table, record_id)

    def __setitem__(self, key, value, /):
        self.set(key, value)

    def __delitem__(self, key, /):
        self.delete(key)

    def __getitem__(self, key, /):
        value = self.get_optional(key)
        if value is None:
            raise KeyError()
        return value

    def __len__(self):
        return self.database.count(self.table)

    def __iter__(self):
        return self.database.iter_ids(self.table)


class MessageRecordStore(DatabaseTableInt[MessageRecord]):
    def __init__(self, database: DatabaseHandle):
        super().__init__(database, "message_records")
        message_codec.build_registry_default()

    def put(self, msg: MessageRecord) -> None:
        self.set(msg.message_id, msg)


class RollRecordCacheFile(CacheFile[int, MessageRecord]):
    def __init__(self, filename: str):
        message_codec.build_registry_default()
        super().__init__(filename)

    def _load(self) -> dict[int, MessageRecord]:
        data = super()._load()
        restored = message_codec.decode_with_hint(data, dict[int, MessageRecord])
        return restored

    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        encoded_data = message_codec.dict_from_dataclass(self.data)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(encoded_data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.path)

    def put(self, msg: MessageRecord) -> None:
        self.set(msg.message_id, msg)

    def dump(self, record_store: MessageRecordStore):
        log.info(f"dumping {len(self)} items into {record_store}...")
        for k, v in self.data.items():
            record_store.seed(k, v)
        log.info(f"complete!")
