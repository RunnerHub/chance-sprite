from __future__ import annotations

import json
import logging
import os
import sqlite3
from collections.abc import Iterator, Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import msgspec
from platformdirs import PlatformDirs

from chance_sprite.sprite_utils import epoch_seconds

from . import APP_NAME
from .message_cache import message_codec
from .message_cache.message_record import MessageRecord

log = logging.getLogger(__name__)


class ReadableFile[K, V](Mapping[K, V]):
    def __init__(self, _dir: Path, filename: str):
        self._dir = _dir
        self.path = _dir / filename
        self._data: dict[K, V] = self._load()

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
        return self._data[key]  # raises KeyError if missing

    def __iter__(self) -> Iterator[K]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


class WriteableFile[K, V](ReadableFile, MutableMapping[K, V]):
    # File I/O (write)
    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.path)

    # Collection methods (write-through)
    def __setitem__(self, key: K, value: Any) -> None:
        self._data[key] = value
        self.save()

    def __delitem__(self, key: K) -> None:
        del self._data[key]  # raises KeyError if missing
        self.save()

    # Helpers
    def set(self, key: K, value: Any) -> None:
        self._data[key] = value
        self.save()

    def remove(self, key: K) -> None:
        self._data.pop(key, None)
        self.save()


@message_codec.register("_CachedEntry")
@dataclass
class _CachedEntry[V]:
    value: V
    expires_at: int  # epoch seconds


class CacheFile[K, V](ReadableFile, MutableMapping[K, V]):
    _cache_dir = Path(PlatformDirs(appname=APP_NAME, appauthor=False).user_cache_dir)

    def __init__(self, filename: str):
        self._dir = self._cache_dir
        self.path = self._cache_dir / filename
        self._data: dict[K, _CachedEntry[V]] = self._load()
        self._purge_expired()

    def _purge_expired(
        self, now: int | None = None
    ) -> int:  # returns number of deleted records
        now = epoch_seconds() if now is None else now
        dead = [k for k, e in self._data.items() if e.expires_at <= now]
        for k in dead:
            del self._data[k]
        return len(dead)

    def _load(self) -> dict[K, _CachedEntry[V]]:
        data = super()._load()
        restored = message_codec.decode_with_hint(data, dict[K, _CachedEntry[V]])
        return restored

    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        encoded_data = message_codec.dict_from_dataclass(self._data)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(encoded_data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.path)

    # public API
    def set(self, key: K, value: V, *, expires_at: int) -> None:
        self._data[key] = _CachedEntry(value=value, expires_at=int(expires_at))
        self.save()

    def __getitem__(self, key: K) -> V:
        e = self._data[key]
        if e.expires_at <= epoch_seconds():
            del self._data[key]
            self.save()
            raise KeyError(key)
        return e.value

    def __setitem__(self, key: K, value: V) -> None:
        raise TypeError("Use set(..., ttl_s=...) or set(..., expires_at=...)")

    def __delitem__(self, key: K) -> None:
        del self._data[key]
        self.save()

    def __iter__(self) -> Iterator[K]:
        # optional: purge here too if you want iteration to hide expired keys
        self._purge_expired()
        return iter(self._data)

    def __len__(self) -> int:
        self._purge_expired()
        return len(self._data)


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

        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=FULL;")

    def init_table_intkey(self, table_name: str):
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
              record_id INTEGER PRIMARY KEY,
              payload BLOB NOT NULL
            )
        """,
        )

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


class UserAvatarStore:
    _table = "identity_cache"

    def __init__(self, database: DatabaseHandle) -> None:
        database.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                user_id     INTEGER NOT NULL,
                guild_id    INTEGER NOT NULL,   -- 0 = global user
                name        TEXT NOT NULL,
                avatar_url  TEXT NOT NULL,
                updated_at  INTEGER NOT NULL,
                PRIMARY KEY (user_id, guild_id)
            );
            """
        )
        self.database = database

    def get_avatar(self, user_id: int, guild_id: int = 0) -> tuple[str, str]:
        row = self.database.conn.execute(
            f"SELECT name, avatar_url FROM {self._table} WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        ).fetchone()
        if row is None and guild_id != 0:
            row = self.database.conn.execute(
                f"SELECT name, avatar_url FROM {self._table} WHERE user_id = ? AND guild_id = 0",
                (user_id,),
            ).fetchone()
        return row

    def update_avatar(self, user_id: int, guild_id: int, name: str, avatar_url: str):
        self.database.conn.execute(
            """
        INSERT INTO identity_cache (user_id, guild_id, name, avatar_url, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
            name = excluded.name,
            avatar_url = excluded.avatar_url,
            updated_at = excluded.updated_at;
            """,
            (
                user_id,
                guild_id,
                name,
                avatar_url,
                epoch_seconds(),
            ),
        )
