"""Persisted app state: import settings + the WebTunes connection.

Stored as one JSON file in the platform config dir. The token is plaintext,
matching the browser extension's storage.local threat model: it is upload-only
scoped and revocable from WebTunes Settings.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

from webtunes_importer.constants import (
    APP_AUTHOR,
    APP_NAME,
    DEFAULT_SERVER_URL,
    DEFAULT_STRICTNESS,
)


@dataclass
class Settings:
    version_pref: str = "none"  # none | studio | live
    quality: str = "opus"  # 128 | 192 | opus | m4a
    strictness: float = DEFAULT_STRICTNESS
    server_url: str = DEFAULT_SERVER_URL


@dataclass
class Connection:
    server_url: str
    token: str
    user_name: str | None = None


@dataclass
class AppConfig:
    settings: Settings = field(default_factory=Settings)
    connection: Connection | None = None


def config_path() -> Path:
    return Path(user_config_dir(APP_NAME, APP_AUTHOR)) / "config.json"


def data_path() -> Path:
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def missed_file_path() -> Path:
    return data_path() / "last-missed.txt"


def load_config() -> AppConfig:
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AppConfig()
    settings = Settings(**{
        k: v for k, v in (raw.get("settings") or {}).items()
        if k in Settings.__dataclass_fields__
    })
    conn_raw = raw.get("connection")
    connection = None
    if conn_raw and conn_raw.get("token") and conn_raw.get("server_url"):
        connection = Connection(**{
            k: v for k, v in conn_raw.items()
            if k in Connection.__dataclass_fields__
        })
    return AppConfig(settings=settings, connection=connection)


def save_config(config: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "settings": asdict(config.settings),
        "connection": asdict(config.connection) if config.connection else None,
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)
