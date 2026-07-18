from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from app.devices.profiles import DEFAULT_DEVICE_MODEL

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config.yaml"


class UsbHint(BaseModel):
    vendor_id: str
    product_id: str


class AppConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    serial_port: str = ""
    baudrate: int = 38400
    device_model: str = DEFAULT_DEVICE_MODEL
    simulator: bool = True
    # Legacy alias — migrated to simulator on load
    mock: bool | None = None
    poll_interval: float = 1.5
    data_dir: str = "data"
    usb_hints: list[UsbHint] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_mock_to_simulator(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "simulator" not in out and "mock" in out:
            out["simulator"] = bool(out["mock"])
        if "simulator" in out:
            out["mock"] = None
        return out

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = ROOT / p
        return p

    def dump_for_yaml(self) -> dict[str, Any]:
        d = self.model_dump(exclude={"mock"})
        return d


def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or DEFAULT_CONFIG
    data: dict[str, Any] = {}
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    return AppConfig(**data)


def save_config(cfg: AppConfig, path: Path | None = None) -> None:
    cfg_path = path or DEFAULT_CONFIG
    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg.dump_for_yaml(), f, allow_unicode=True, sort_keys=False)
