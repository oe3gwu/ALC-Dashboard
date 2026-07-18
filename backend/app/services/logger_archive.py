from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.protocol.models import LoggerData

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class LoggerArchive:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "logger"
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_id(self, session_id: str) -> str:
        if not _SESSION_ID_RE.fullmatch(session_id):
            raise ValueError("invalid session id")
        return session_id

    def save(self, logger: LoggerData, label: str | None = None) -> dict[str, Any]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"ch{logger.channel + 1}_{label or 'session'}_{ts}"
        payload = logger.to_dict()
        payload["saved_at"] = datetime.now().isoformat(timespec="seconds")

        json_path = self.root / f"{base}.json"
        csv_path = self.root / f"{base}.csv"

        with json_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        with csv_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["index", "time_s", "voltage_V", "current_mA", "capacity_mAh", "marker"])
            for i, s in enumerate(logger.samples):
                w.writerow(
                    [
                        i,
                        i * 5,
                        "" if s.voltage_V is None else f"{s.voltage_V:.4f}",
                        "" if s.current_mA is None else f"{s.current_mA:.2f}",
                        "" if s.capacity_mAh is None else f"{s.capacity_mAh:.4f}",
                        s.marker or "",
                    ]
                )

        return {
            "id": base,
            "json": str(json_path.name),
            "csv": str(csv_path.name),
            "channel": logger.channel,
            "sample_count": len(logger.samples),
            "saved_at": payload["saved_at"],
        }

    def list_sessions(self) -> list[dict[str, Any]]:
        items: list[tuple[str, float, dict[str, Any]]] = []
        for path in self.root.glob("*.json"):
            try:
                with path.open(encoding="utf-8") as f:
                    data = json.load(f)
                items.append(
                    (
                        str(data.get("saved_at") or ""),
                        path.stat().st_mtime,
                        {
                            "id": path.stem,
                            "json": path.name,
                            "channel": data.get("channel"),
                            "sample_count": data.get("sample_count"),
                            "saved_at": data.get("saved_at"),
                            "header": data.get("header"),
                        },
                    )
                )
            except Exception:
                continue
        items.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [meta for _, _, meta in items]

    def load(self, session_id: str) -> dict[str, Any]:
        session_id = self._safe_id(session_id)
        path = self.root / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(session_id)
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    def path_for(self, session_id: str, ext: str) -> Path:
        session_id = self._safe_id(session_id)
        path = self.root / f"{session_id}.{ext}"
        if not path.exists():
            raise FileNotFoundError(session_id)
        return path

    def delete(self, session_id: str) -> None:
        session_id = self._safe_id(session_id)
        json_path = self.root / f"{session_id}.json"
        if not json_path.exists():
            raise FileNotFoundError(session_id)
        for ext in ("json", "csv", "pdf"):
            path = self.root / f"{session_id}.{ext}"
            if path.exists():
                path.unlink()

    def delete_all(self) -> int:
        ids = {p.stem for p in self.root.glob("*.json")}
        for session_id in ids:
            try:
                self.delete(session_id)
            except (FileNotFoundError, ValueError):
                continue
        # orphan exports without json
        for path in self.root.iterdir():
            if path.is_file() and path.suffix in {".csv", ".pdf", ".json"}:
                path.unlink(missing_ok=True)
        return len(ids)
