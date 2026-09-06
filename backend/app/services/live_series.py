"""In-process live U/I/C series — last 24 hours per channel, RAM only."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Any, Literal

MAX_AGE_S = 24 * 3600
MAX_POINTS = 24 * 3600  # 1 Hz cap
_MAX_AGE_MS = MAX_AGE_S * 1000

MetricKey = Literal["v", "i", "c"]
Point = tuple[int, float, float | None, float | None, float | None]
PendingSlot = dict[str, Any]
PendingState = dict[str, PendingSlot]

# Match frontend/src/liveSeries.ts — hold serial glitches instead of drawing axis needles.
# Absolute caps apply at high levels; relative band catches trickle/top-off needles
# (e.g. 93 mA → 45 mA) that stay well below the 60 mA absolute jump.
GLITCH_V_ABS = 0.15  # V
GLITCH_V_REL = 0.04
GLITCH_V_FLOOR = 0.05
GLITCH_I_ABS = 60.0  # mA
GLITCH_I_REL = 0.15
GLITCH_I_FLOOR = 10.0
GLITCH_C_ABS = 20.0  # mAh
GLITCH_C_REL = 0.03
GLITCH_C_FLOOR = 5.0
CONFIRM_DEFAULT = 3
CAPACITY_ABSURD = 200000.0  # 200 Ah — wire garbage, not a 1 s process step
# Capacity barely moves at 1 Hz (~mAh/s). Jumps beyond this are serial spikes, never accept.
CAPACITY_JUMP_ABS = 80.0
CAPACITY_JUMP_REL = 0.2
SCRUB_RUN_MAX = 20
STABLE_I_MA = 20.0  # trickle/top-off is often 50–100 mA; 120 hid those plateaus
# After Stop/Start, ignore leftover high C until a fresh low baseline or timeout.
CAPACITY_FRESH_TIMEOUT_MS = 15_000


def _now_ms(now_ms: int | None) -> int:
    if now_ms is not None:
        return int(now_ms)
    return int(time.time() * 1000)


def is_idle_channel(ch: dict[str, Any] | None) -> bool:
    if not ch:
        return True
    return bool(ch.get("idle")) or ch.get("stage_name") == "Leerlauf"


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def thresh_for(key: MetricKey, ref: float | None = None) -> float:
    if key == "v":
        abs_t, rel, floor = GLITCH_V_ABS, GLITCH_V_REL, GLITCH_V_FLOOR
    elif key == "i":
        abs_t, rel, floor = GLITCH_I_ABS, GLITCH_I_REL, GLITCH_I_FLOOR
    else:
        abs_t, rel, floor = GLITCH_C_ABS, GLITCH_C_REL, GLITCH_C_FLOOR
    if ref is None or not math.isfinite(ref):
        return abs_t
    return max(floor, min(abs_t, rel * abs(ref)))


def metric_abrupt(prev: float | None, nxt: float | None, key: MetricKey) -> bool:
    if prev is None or nxt is None:
        return (prev is None) != (nxt is None)
    return abs(prev - nxt) >= thresh_for(key, prev)


def is_collapsed_value(value: float | None, key: MetricKey) -> bool:
    if value is None:
        return True
    if key == "i":
        return abs(value) < 40.0
    if key == "c":
        return value < 5.0
    return value < 0.25


def is_stable_value(value: float | None, key: MetricKey) -> bool:
    if value is None:
        return False
    if key == "i":
        return abs(value) >= STABLE_I_MA
    if key == "c":
        return value >= 30.0
    return value >= 1.2


def is_implausible_capacity_jump(prev: float | None, nxt: float | None) -> bool:
    """True if C changed faster than any real 1 Hz process (e.g. 5000 → 1_000_000)."""
    if prev is None or not math.isfinite(prev):
        return False
    if nxt is None or not math.isfinite(nxt):
        return is_stable_value(prev, "c")
    return abs(nxt - prev) >= max(CAPACITY_JUMP_ABS, CAPACITY_JUMP_REL * abs(prev))


def is_capacity_down_reset(prev: float | None, nxt: float | None) -> bool:
    """New process / counter reset: capacity dropped hard (not an upward serial spike)."""
    if not is_implausible_capacity_jump(prev, nxt):
        return False
    if prev is None or not math.isfinite(prev):
        return False
    if nxt is None or not math.isfinite(nxt):
        return is_stable_value(prev, "c")
    return nxt < prev


def is_metric_collapse(key: MetricKey, prev: float | None, nxt: float | None) -> bool:
    if is_stable_value(prev, key) and is_collapsed_value(nxt, key):
        return True
    if key == "c":
        return is_implausible_capacity_jump(prev, nxt)
    return False


def near_metric(a: float | None, b: float | None, key: MetricKey) -> bool:
    return not metric_abrupt(a, b, key)


def sanitize_raw(
    voltage: Any, current: Any, capacity: Any
) -> tuple[float | None, float | None, float | None]:
    v = _finite(voltage)
    i = _finite(current)
    c = _finite(capacity)
    if c is not None and (c < 0 or c > CAPACITY_ABSURD):
        c = None
    if i is not None and abs(i) > 20000:
        i = None
    if v is not None and (v < -1 or v > 80):
        v = None
    return v, i, c


def resolve_metric(
    pending: PendingState,
    key: MetricKey,
    prev: float | None,
    raw: float | None,
) -> float | None:
    # V/I collapses stay held. Capacity down-resets unlock after confirmed ticks;
    # upward capacity spikes never unlock.
    if is_metric_collapse(key, prev, raw):
        slot = pending.get(key)
        confirms = int(slot["confirms"]) + 1 if slot else 1
        if key == "c" and is_capacity_down_reset(prev, raw) and confirms >= CONFIRM_DEFAULT:
            pending.pop(key, None)
            return raw
        pending[key] = {"value": raw, "confirms": confirms}
        return prev

    slot = pending.get(key)
    if slot:
        if is_metric_collapse(key, prev, slot.get("value")):
            if key == "c" and is_capacity_down_reset(prev, slot.get("value")):
                if is_capacity_down_reset(prev, raw) or is_collapsed_value(raw, "c"):
                    confirms = int(slot["confirms"]) + 1
                    if confirms >= CONFIRM_DEFAULT:
                        pending.pop(key, None)
                        return raw
                    pending[key] = {"value": raw, "confirms": confirms}
                    return prev
            if near_metric(prev, raw, key):
                pending.pop(key, None)
                return raw
            pending[key] = {"value": raw, "confirms": int(slot["confirms"]) + 1}
            return prev

        if near_metric(slot.get("value"), raw, key):
            confirms = int(slot["confirms"]) + 1
            if confirms >= CONFIRM_DEFAULT:
                pending.pop(key, None)
                return raw
            pending[key] = {"value": raw, "confirms": confirms}
            return prev
        if near_metric(prev, raw, key):
            pending.pop(key, None)
            return raw
        pending[key] = {"value": raw, "confirms": 1}
        return prev

    if metric_abrupt(prev, raw, key):
        # First capacity reading after unknown/null is a baseline, not a glitch.
        if key == "c" and prev is None and raw is not None:
            pending.pop(key, None)
            return raw
        pending[key] = {"value": raw, "confirms": 1}
        return prev

    return raw


def resolve_sample(
    pending: PendingState,
    prev: tuple[float | None, float | None, float | None] | None,
    incoming: tuple[Any, Any, Any],
) -> tuple[float | None, float | None, float | None]:
    raw = sanitize_raw(*incoming)
    if prev is None:
        pending.clear()
        return raw
    sample = (
        resolve_metric(pending, "v", prev[0], raw[0]),
        resolve_metric(pending, "i", prev[1], raw[1]),
        resolve_metric(pending, "c", prev[2], raw[2]),
    )
    if not pending:
        pending.clear()
    return sample


def _scrub_isolated(key: MetricKey, values: list[float | None]) -> None:
    """Original 1-sample sandwich: if neighbors agree and the middle jumped, hold left."""
    n = len(values)
    for i in range(1, n - 1):
        if near_metric(values[i - 1], values[i + 1], key) and metric_abrupt(values[i - 1], values[i], key):
            values[i] = values[i - 1]


def _scrub_metric(key: MetricKey, values: list[float | None]) -> None:
    _scrub_isolated(key, values)
    n = len(values)
    i = 1
    while i < n - 1:
        # Trickle plateaus (~90 mA) are not "stable" at the old 120 mA gate, but they
        # must still be eligible as the left side of a sandwich spike.
        if is_collapsed_value(values[i - 1], key):
            i += 1
            continue
        if not metric_abrupt(values[i - 1], values[i], key):
            i += 1
            continue

        run_start = i
        while i < n and metric_abrupt(values[run_start - 1], values[i], key):
            i += 1
        run_len = i - run_start
        if run_len < 1 or run_len > SCRUB_RUN_MAX or i >= n:
            continue

        left = values[run_start - 1]
        right = values[i]
        if is_collapsed_value(left, key) or not near_metric(left, right, key):
            continue

        collapse_run = all(is_collapsed_value(values[run_start + j], key) for j in range(run_len))
        fill = True
        if not collapse_run:
            for j in range(run_len):
                if not metric_abrupt(left, values[run_start + j], key):
                    fill = False
                    break
        if not fill:
            continue

        for j in range(run_len):
            t = (j + 1) / (run_len + 1)
            if left is not None and right is not None:
                values[run_start + j] = left + (right - left) * t
            else:
                values[run_start + j] = left


def hold_collapses(values: list[float | None], key: MetricKey) -> None:
    """Hold brief needles; keep sustained capacity down-resets (new process)."""
    n = len(values)
    i = 1
    while i < n:
        if not is_metric_collapse(key, values[i - 1], values[i]):
            i += 1
            continue
        left = values[i - 1]
        run_start = i
        while i < n and is_metric_collapse(key, left, values[i]):
            i += 1
        recovered = i < n and near_metric(left, values[i], key)
        # Capacity: only rewrite recovered sandwich needles. Trailing/sustained
        # down-resets are kept (resolve_metric already filters brief tips).
        hold = recovered if key == "c" else True
        if hold:
            for j in range(run_start, i):
                values[j] = left


def scrub_points(points: list[Point]) -> list[Point]:
    """Fill sandwich spikes and hold remaining collapses. Does not mutate `points`."""
    if len(points) < 2:
        return list(points)
    voltages = [p[2] for p in points]
    currents = [p[3] for p in points]
    capacities = [p[4] for p in points]
    if len(points) >= 3:
        _scrub_metric("v", voltages)
        _scrub_metric("i", currents)
        _scrub_metric("c", capacities)
    hold_collapses(voltages, "v")
    hold_collapses(currents, "i")
    hold_collapses(capacities, "c")
    return [
        (p[0], p[1], voltages[idx], currents[idx], capacities[idx]) for idx, p in enumerate(points)
    ]


class _ChannelSeries:
    __slots__ = ("t0_ms", "points", "pending")

    def __init__(self, t0_ms: int) -> None:
        self.t0_ms = t0_ms
        # (wall_ms, t_s, v, i, c)
        self.points: deque[Point] = deque(maxlen=MAX_POINTS)
        self.pending: PendingState = {}


class LiveSeriesStore:
    """Ring buffer of live samples. Not tied to hostname, origin, or browser."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channels: dict[int, _ChannelSeries] = {}
        # After Stop, skip ingest until the channel is seen idle (avoids 1–2 leftover ticks).
        self._hold_off: set[int] = set()
        # After Stop/Start, suppress stale high capacity until a fresh low baseline.
        self._capacity_fresh_since: dict[int, int] = {}

    def clear(self, channel: int, *, hold_off: bool = False) -> None:
        with self._lock:
            ch = int(channel)
            self._channels.pop(ch, None)
            self._capacity_fresh_since[ch] = _now_ms(None)
            if hold_off:
                self._hold_off.add(ch)
            else:
                self._hold_off.discard(ch)

    def clear_all(self) -> None:
        with self._lock:
            self._channels.clear()
            self._hold_off.clear()
            self._capacity_fresh_since.clear()

    def _arm_capacity_locked(
        self, ch: int, cap: float | None, *, running: bool, now_ms: int
    ) -> float | None:
        since = self._capacity_fresh_since.get(ch)
        if since is None:
            return cap
        if not running:
            return None
        if (
            cap is None
            or not is_stable_value(cap, "c")
            or now_ms - since >= CAPACITY_FRESH_TIMEOUT_MS
        ):
            self._capacity_fresh_since.pop(ch, None)
            return cap
        return None

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
                if ch in self._hold_off:
                    if is_idle_channel(c):
                        self._hold_off.discard(ch)
                    continue
                if is_idle_channel(c):
                    continue
                m = meas_by_ch.get(ch, {})
                series = self._channels.get(ch)
                if series is None:
                    series = _ChannelSeries(ts)
                    self._channels[ch] = series
                t = (ts - series.t0_ms) / 1000.0
                prev = None
                if series.points:
                    last = series.points[-1]
                    prev = (last[2], last[3], last[4])
                v_raw, i_raw, c_raw = sanitize_raw(
                    m.get("voltage_V"), m.get("current_mA"), m.get("capacity_mAh")
                )
                c_raw = self._arm_capacity_locked(ch, c_raw, running=True, now_ms=ts)
                v, i, cap = resolve_sample(
                    series.pending,
                    prev,
                    (v_raw, i_raw, c_raw),
                )
                series.points.append((ts, t, v, i, cap))
                self._scrub_tail_locked(series)

    def snapshot(self, now_ms: int | None = None) -> dict[str, Any]:
        ts = _now_ms(now_ms)
        with self._lock:
            self._prune_locked(ts)
            out: dict[str, Any] = {}
            for ch, series in self._channels.items():
                cleaned = scrub_points(list(series.points))
                series.points.clear()
                series.points.extend(cleaned)
                out[str(ch)] = {
                    "t0": series.t0_ms,
                    "points": [{"t": t, "v": v, "i": i, "c": cap} for _wall, t, v, i, cap in cleaned],
                }
            return {"channels": out}

    def _scrub_tail_locked(self, series: _ChannelSeries) -> None:
        n = len(series.points)
        if n < 3:
            return
        window = min(n, SCRUB_RUN_MAX * 2 + 3)
        pts = list(series.points)
        head, tail = pts[:-window], pts[-window:]
        series.points.clear()
        series.points.extend(head)
        series.points.extend(scrub_points(tail))

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
