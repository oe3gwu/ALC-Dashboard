from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.protocol.constants import BATTERY_TYPES
from app.protocol.models import BatteryDbEntry

SLOT_COUNT = 40
ENTRY_KEYS = (
    "slot",
    "name",
    "battery_type",
    "cells",
    "discharge_mA",
    "charge_mA",
    "capacity_mAh",
    "pause_s",
    "forming_mA",
    "flags",
    "full_factor",
)


def empty_entry(slot: int) -> dict[str, Any]:
    """Cleared local preset (like an unused ALC slot), not factory NiMH defaults."""
    return {
        "slot": slot,
        "name": "",
        "battery_type": 0xFF,
        "battery_type_name": BATTERY_TYPES[0xFF],
        "cells": 1,
        "discharge_mA": 0.0,
        "charge_mA": 0.0,
        "capacity_mAh": 0.0,
        "pause_s": 0,
        "forming_mA": 0.0,
        "flags": 0,
        "full_factor": 250,
    }


def normalize_entry(raw: dict[str, Any], slot: int | None = None) -> dict[str, Any]:
    s = int(slot if slot is not None else raw.get("slot", 0))
    if s < 0 or s >= SLOT_COUNT:
        raise ValueError(f"Ungültiger Slot: {s}")
    base = empty_entry(s)
    for key in ENTRY_KEYS:
        if key == "slot":
            continue
        if key in raw:
            base[key] = raw[key]
    base["slot"] = s
    base["name"] = str(base.get("name") or "")[:9]
    # Keep 0xFF (empty „—“) and 0x00 (NiCd); only fall back when missing/None
    bt = base.get("battery_type")
    base["battery_type"] = int(bt) if bt is not None and bt != "" else 0xFF
    base["cells"] = int(base.get("cells") or 1)
    base["discharge_mA"] = float(base.get("discharge_mA") or 0)
    base["charge_mA"] = float(base.get("charge_mA") or 0)
    base["capacity_mAh"] = float(base.get("capacity_mAh") or 0)
    base["pause_s"] = int(base.get("pause_s") or 0)
    base["forming_mA"] = float(base.get("forming_mA") or 0)
    base["flags"] = int(base.get("flags") or 0)
    base["full_factor"] = int(base.get("full_factor") if base.get("full_factor") is not None else 250)
    base["battery_type_name"] = BATTERY_TYPES.get(base["battery_type"], "?")
    return base


def entry_to_model(d: dict[str, Any]) -> BatteryDbEntry:
    n = normalize_entry(d)
    return BatteryDbEntry(**{k: n[k] for k in ENTRY_KEYS})


class BatteryDbArchive:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "battery-db.json"
        data_dir.mkdir(parents=True, exist_ok=True)

    def _ensure(self) -> None:
        if not self.path.exists():
            self.save([empty_entry(i) for i in range(SLOT_COUNT)])

    def load(self) -> list[dict[str, Any]]:
        self._ensure()
        with self.path.open(encoding="utf-8") as f:
            data = json.load(f)
        raw_entries = data.get("entries") if isinstance(data, dict) else data
        if not isinstance(raw_entries, list):
            raise ValueError("Ungültiges battery-db.json Format")
        by_slot: dict[int, dict[str, Any]] = {}
        for item in raw_entries:
            if not isinstance(item, dict):
                continue
            try:
                n = normalize_entry(item)
                by_slot[n["slot"]] = n
            except ValueError:
                continue
        return [by_slot.get(i) or empty_entry(i) for i in range(SLOT_COUNT)]

    def save(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [normalize_entry(e, slot=i) for i, e in enumerate(entries[:SLOT_COUNT])]
        while len(normalized) < SLOT_COUNT:
            normalized.append(empty_entry(len(normalized)))
        payload = {"version": 1, "entries": [{k: e[k] for k in ENTRY_KEYS} for e in normalized]}
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return [normalize_entry(e) for e in normalized]

    def get(self, slot: int) -> dict[str, Any]:
        if slot < 0 or slot >= SLOT_COUNT:
            raise ValueError(f"Ungültiger Slot: {slot}")
        return self.load()[slot]

    def put(self, slot: int, raw: dict[str, Any]) -> dict[str, Any]:
        entries = self.load()
        entries[slot] = normalize_entry(raw, slot=slot)
        self.save(entries)
        return entries[slot]

    def reset(self, slot: int) -> dict[str, Any]:
        """Reset one slot to empty defaults (local archive only)."""
        return self.put(slot, empty_entry(slot))

    def replace_all(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.save(entries)

    def to_json_bytes(self) -> bytes:
        self._ensure()
        return self.path.read_bytes()
