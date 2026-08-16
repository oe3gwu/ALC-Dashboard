"""In-process 6h live series ring buffer."""

from __future__ import annotations

from app.services.live_series import MAX_AGE_S, MAX_POINTS, LiveSeriesStore


def _ch(idle: bool, stage: str = "Laden") -> dict:
    return {
        "idle": idle,
        "stage_name": "Leerlauf" if idle else stage,
        "channel": 99,
    }


def _m(v: float, i: float, c: float) -> dict:
    return {"channel": 99, "voltage_V": v, "current_mA": i, "capacity_mAh": c}


def test_ingest_running_creates_series():
    store = LiveSeriesStore()
    t0 = 1_700_000_000_000
    store.ingest([_ch(False)], [_m(1.25, 500, 10)], now_ms=t0)
    snap = store.snapshot(now_ms=t0)
    pts = snap["channels"]["0"]["points"]
    assert snap["channels"]["0"]["t0"] == t0
    assert pts == [{"t": 0.0, "v": 1.25, "i": 500, "c": 10}]


def test_list_index_overrides_wire_channel_byte():
    store = LiveSeriesStore()
    t0 = 1_000
    store.ingest(
        [_ch(True), _ch(False)],
        [_m(0, 0, 0), _m(3.7, 200, 5)],
        now_ms=t0,
    )
    snap = store.snapshot(now_ms=t0)
    assert "0" not in snap["channels"]
    assert len(snap["channels"]["1"]["points"]) == 1
    assert snap["channels"]["1"]["points"][0]["v"] == 3.7


def test_idle_does_not_append_or_clear():
    store = LiveSeriesStore()
    t0 = 5_000
    store.ingest([_ch(False)], [_m(4.1, 800, 20)], now_ms=t0)
    store.ingest([_ch(False)], [_m(4.2, 790, 21)], now_ms=t0 + 1000)
    store.ingest([_ch(True)], [_m(1.25, 0, 21)], now_ms=t0 + 2000)
    pts = store.snapshot(now_ms=t0 + 2000)["channels"]["0"]["points"]
    assert len(pts) == 2
    assert pts[-1]["v"] == 4.2


def test_clear_drops_channel():
    store = LiveSeriesStore()
    store.ingest([_ch(False), _ch(False)], [_m(1, 1, 1), _m(2, 2, 2)], now_ms=10)
    store.clear(0)
    snap = store.snapshot(now_ms=10)
    assert "0" not in snap["channels"]
    assert "1" in snap["channels"]


def test_empty_snapshot_keeps_series():
    store = LiveSeriesStore()
    t0 = 8_000
    store.ingest([_ch(False)], [_m(3.6, 100, 1)], now_ms=t0)
    store.ingest([], [], now_ms=t0 + 1000)
    assert "0" in store.snapshot(now_ms=t0 + 1000)["channels"]


def test_age_prune_drops_old_finished_series():
    store = LiveSeriesStore()
    t0 = 1_000_000
    store.ingest([_ch(False)], [_m(3.6, 100, 1)], now_ms=t0)
    later = t0 + (MAX_AGE_S * 1000) + 1
    assert store.snapshot(now_ms=later)["channels"] == {}


def test_age_prune_keeps_recent_tail():
    store = LiveSeriesStore()
    t0 = 2_000_000
    store.ingest([_ch(False)], [_m(3.0, 100, 1)], now_ms=t0)
    store.ingest([_ch(False)], [_m(3.1, 100, 2)], now_ms=t0 + 1000)
    later = t0 + (MAX_AGE_S * 1000) + 500
    store.ingest([_ch(False)], [_m(3.2, 100, 3)], now_ms=later)
    pts = store.snapshot(now_ms=later)["channels"]["0"]["points"]
    assert len(pts) == 1
    assert pts[0]["v"] == 3.2
    assert pts[0]["t"] == (later - t0) / 1000.0


def test_maxlen_caps_at_six_hours_of_1hz():
    store = LiveSeriesStore()
    t0 = 3_000_000
    for n in range(MAX_POINTS + 25):
        store.ingest([_ch(False)], [_m(1.0, float(n), n)], now_ms=t0 + n * 1000)
    pts = store.snapshot(now_ms=t0 + (MAX_POINTS + 24) * 1000)["channels"]["0"]["points"]
    assert len(pts) == MAX_POINTS
    assert pts[0]["i"] == 25
    assert pts[-1]["i"] == MAX_POINTS + 24
