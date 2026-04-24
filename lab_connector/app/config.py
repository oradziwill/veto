from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    veto_base_url: str
    veto_device_id: int
    veto_ingest_token: str

    listen_host: str = "0.0.0.0"
    listen_port: int = 2575
    sample_identifier_scheme: str = "barcode"

    outbox_db_path: Path = _ROOT / "data" / "outbox.sqlite3"
    health_host: str = "127.0.0.1"
    health_port: int = 8765
    outbox_poll_sec: float = 5.0
    retry_backoff_sec: list[int] = [60, 300, 900, 3600]
    max_delivery_attempts: int = 15

    agent_enabled: bool = False
    dm_base_url: str = ""
    dm_bearer_token: str = ""
    dm_node_id: str = "lab-connector-node"
    dm_node_name: str = "Lab Connector Node"
    dm_inventory_poll_sec: float = 60.0
    dm_command_poll_sec: float = 5.0
    dm_clinic_id: int | None = None

    @field_validator("outbox_db_path", mode="before")
    @classmethod
    def resolve_db_path(cls, v: str | Path) -> Path:
        p = Path(v)
        if not p.is_absolute():
            p = _ROOT / p
        return p

    @field_validator("retry_backoff_sec", mode="before")
    @classmethod
    def parse_backoff(cls, v: str | list[int]) -> list[int]:
        if isinstance(v, list):
            return [int(x) for x in v]
        parts = [p.strip() for p in str(v).split(",") if p.strip()]
        return [int(x) for x in parts]

    @field_validator("veto_base_url")
    @classmethod
    def strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    def ingest_url(self) -> str:
        return f"{self.veto_base_url}/api/lab-devices/{self.veto_device_id}/ingest/"

    @field_validator("dm_base_url")
    @classmethod
    def strip_dm_slash(cls, v: str) -> str:
        return v.rstrip("/")
