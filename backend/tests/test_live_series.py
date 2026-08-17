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
    later = t0 + (MAX_AGE_S * 1000) + 1500
    store.ingest([_ch(False)], [_m(3.2, 100, 3)], now_ms=later)
    snap = store.snapshot(now_ms=later)["channels"]["0"]
    pts = snap["points"]
    assert len(pts) == 1
    assert pts[0]["v"] == 3.2
    # Gap > 6 h dropped the old series; a still-running channel starts a new t0.
    assert snap["t0"] == later
    assert pts[0]["t"] == 0.0


def test_collapse_to_zero_holds_previous_voltage_and_current():
    """Serial glitch 11.4 V / 1400 mA → 0/0 must not draw axis needles."""
    store = LiveSeriesStore()
    t0 = 10_000
    store.ingest([_ch(False)], [_m(11.396, 1400.0, 4162.3)], now_ms=t0)
    store.ingest([_ch(False)], [_m(0.0, 0.0, 0.0)], now_ms=t0 + 1000)
    store.ingest([_ch(False)], [_m(11.390, 1400.0, 4162.7)], now_ms=t0 + 2000)
    pts = store.snapshot(now_ms=t0 + 2000)["channels"]["0"]["points"]
    assert len(pts) == 3
    assert pts[1]["v"] == 11.396
    assert pts[1]["i"] == 1400.0
    assert pts[1]["c"] == 4162.3
    assert pts[2]["v"] == 11.390
    assert pts[2]["i"] == 1400.0


def test_repeated_zero_needles_stay_off_the_axis():
    store = LiveSeriesStore()
    t0 = 20_000
    v, i, c = 11.4, 1400.0, 4000.0
    for n in range(40):
        if n > 0 and n % 7 == 0:
            store.ingest([_ch(False)], [_m(0.0, 0.0, 0.0)], now_ms=t0 + n * 1000)
        else:
            c += 0.4
            store.ingest([_ch(False)], [_m(v, i, c)], now_ms=t0 + n * 1000)
    pts = store.snapshot(now_ms=t0 + 39_000)["channels"]["0"]["points"]
    assert len(pts) == 40
    for p in pts:
        assert p["v"] is not None and p["v"] >= 1.2
        assert p["i"] is not None and abs(p["i"]) >= 120
        assert p["c"] is not None and p["c"] >= 30


def test_scrub_fills_interior_zero_needles():
    from app.services.live_series import scrub_points

    points = [
        (0, 0.0, 11.4, 1400.0, 100.0),
        (1, 1.0, 0.0, 0.0, 0.0),
        (2, 2.0, 11.4, 1400.0, 100.4),
        (3, 3.0, 0.0, 0.0, 0.0),
        (4, 4.0, 11.4, 1400.0, 100.8),
    ]
    cleaned = scrub_points(points)
    assert cleaned[1][2] == 11.4
    assert cleaned[1][3] == 1400.0
    assert cleaned[3][2] == 11.4
    assert cleaned[3][3] == 1400.0


def test_real_voltage_step_accepted_after_confirms():
    store = LiveSeriesStore()
    t0 = 30_000
    store.ingest([_ch(False)], [_m(12.6, 200.0, 50.0)], now_ms=t0)
    for n in range(1, 5):
        store.ingest([_ch(False)], [_m(4.2, 200.0, 50.0 + n)], now_ms=t0 + n * 1000)
    pts = store.snapshot(now_ms=t0 + 4000)["channels"]["0"]["points"]
    # First sample 12.6; next two held; third matching tick accepts 4.2.
    assert pts[0]["v"] == 12.6
    assert pts[1]["v"] == 12.6
    assert pts[2]["v"] == 12.6
    assert pts[3]["v"] == 4.2
    assert pts[4]["v"] == 4.2


def test_maxlen_caps_at_six_hours_of_1hz():
    store = LiveSeriesStore()
    t0 = 3_000_000
    for n in range(MAX_POINTS + 25):
        store.ingest([_ch(False)], [_m(3.7, 500.0, 100.0)], now_ms=t0 + n * 1000)
    pts = store.snapshot(now_ms=t0 + (MAX_POINTS + 24) * 1000)["channels"]["0"]["points"]
    assert len(pts) == MAX_POINTS
    assert pts[0]["t"] == 25.0
    assert pts[-1]["t"] == float(MAX_POINTS + 24)
