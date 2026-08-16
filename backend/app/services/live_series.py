"""In-process live U/I/C series — last 6 hours per channel, RAM only."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

MAX_AGE_S = 6 * 3600
MAX_POINTS = 6 * 3600  # 1 Hz cap
_MAX_AGE_MS = MAX_AGE_S * 1000


def _now_ms(now_ms: int | None) -> int:
    if now_ms is not None:
        return int(now_ms)
    return int(time.time() * 1000)


def is_idle_channel(ch: dict[str, Any] | None) -> bool:
    if not ch:
        return True
    return bool(ch.get("idle")) or ch.get("stage_name") == "Leerlauf"


class _ChannelSeries:
    __slots__ = ("t0_ms", "points")

    def __init__(self, t0_ms: int) -> None:
        self.t0_ms = t0_ms
        # (wall_ms, t_s, v, i, c)
        self.points: deque[tuple[int, float, float | None, float | None, float | None]] = deque(
            maxlen=MAX_POINTS
        )


class LiveSeriesStore:
    """Ring buffer of live samples. Not tied to hostname, origin, or browser."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channels: dict[int, _ChannelSeries] = {}

    def clear(self, channel: int) -> None:
        with self._lock:
            self._channels.pop(int(channel), None)

    def clear_all(self) -> None:
        with self._lock:
            self._channels.clear()

    def ingest(
        self,
        channels: list[dict[str, Any]] | None,
        measurements: list[dict[str, Any]] | None,
        now_ms: int | None = None,
    ) -> None:
        ts = _now_ms(now_ms)
        with self._lock:
            self._prune_locked(ts)
            if not channels:
                return
            ch_list = [{**c, "channel": idx} for idx, c in enumerate(channels)]
            meas_in = list(measurements or [])
            if len(meas_in) == len(ch_list):
                meas_list = [{**m, "channel": idx} for idx, m in enumerate(meas_in)]
            else:
                meas_list = meas_in
            meas_by_ch = {int(m.get("channel", i)): m for i, m in enumerate(meas_list)}

            for c in ch_list:
                ch = int(c["channel"])
                if is_idle_channel(c):
                    continue
                m = meas_by_ch.get(ch, {})
                series = self._channels.get(ch)
                if series is None:
                    series = _ChannelSeries(ts)
                    self._channels[ch] = series
                t = (ts - series.t0_ms) / 1000.0
                series.points.append(
                    (
                        ts,
                        t,
                        m.get("voltage_V"),
                        m.get("current_mA"),
                        m.get("capacity_mAh"),
                    )
                )

    def snapshot(self, now_ms: int | None = None) -> dict[str, Any]:
        ts = _now_ms(now_ms)
        with self._lock:
            self._prune_locked(ts)
            out: dict[str, Any] = {}
            for ch, series in self._channels.items():
                out[str(ch)] = {
                    "t0": series.t0_ms,
                    "points": [
                        {"t": t, "v": v, "i": i, "c": cap} for _wall, t, v, i, cap in series.points
                    ],
                }
            return {"channels": out}

    def _prune_locked(self, now_ms: int) -> None:
        cutoff = now_ms - _MAX_AGE_MS
        drop: list[int] = []
        for ch, series in self._channels.items():
            pts = series.points
            while pts and pts[0][0] < cutoff:
                pts.popleft()
            if not pts:
                drop.append(ch)
        for ch in drop:
            self._channels.pop(ch, None)
