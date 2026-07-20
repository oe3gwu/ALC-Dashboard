"""Roundtrip-Tests: Alc8xxxClient ↔ Simulator (ELVjournal 8000/8500 Expert)."""

from __future__ import annotations

from app.protocol.alc8xxx import models as wire
from app.protocol.alc8xxx.client import Alc8xxxClient
from app.protocol.alc8xxx.constants import IDENT_8000_PLUS, IDENT_8500
from app.protocol.alc8xxx.framing import build_frame, parse_frame
from app.protocol.alc8xxx.simulator import Alc8xxxSimulator
from app.protocol.models import ChannelParams


def test_channel_encode_has_no_full_factor_byte():
    p = ChannelParams(
        channel=0,
        battery_type=0x01,
        cells=4,
        capacity_mAh=2000,
        charge_mA=500,
        discharge_mA=250,
        program=0x01,
        full_factor=100,  # must not appear on wire
    )
    raw = wire.encode_channel_set(p)
    assert len(raw) == 18
    decoded = wire.decode_channel_params(raw)
    assert decoded.full_factor == 250
    assert decoded.charge_mA == 500
    assert decoded.cells == 4


def test_framing_roundtrip():
    payload = bytes([ord("t")])
    frame = build_frame(payload)
    assert parse_frame(frame) == payload


def test_8500_expert_idle_measurements_match_8500_2():
    sim = Alc8xxxSimulator(channel_count=4, has_logger=True, ident_prefix=IDENT_8500)
    c = Alc8xxxClient(sim, channel_count=4, has_logger=True)
    m = c.get_measurements()
    assert len(m) == 4
    assert m[0].voltage_V == 5.0  # 1.25 V × 4 cells
    assert m[0].current_mA == 0.0
    assert m[0].capacity_mAh == 0.0


def test_8000_plus_three_channels():
    sim = Alc8xxxSimulator(channel_count=3, has_logger=False, ident_prefix=IDENT_8000_PLUS)
    c = Alc8xxxClient(sim, channel_count=3, has_logger=False)
    assert len(c.get_measurements()) == 3
    assert sim.ident.startswith("e")


def test_params_and_start_stop():
    c = Alc8xxxClient(Alc8xxxSimulator(channel_count=4, has_logger=True), channel_count=4, has_logger=True)
    p = ChannelParams(
        channel=0,
        battery_type=0x01,
        cells=4,
        capacity_mAh=2000,
        charge_mA=500,
        discharge_mA=250,
        program=0x01,
        full_factor=250,
    )
    echoed = c.set_channel_params(p)
    assert echoed.cells == 4
    assert echoed.full_factor == 250
    assert echoed.stage_name == "Leerlauf"
    st = c.set_activity(0, stop=False)
    assert st.stage_name == "Laden"
    m = c.get_measurements()[0]
    assert m.voltage_V is not None and m.voltage_V > 0
    assert m.current_mA is not None and m.current_mA > 0
    c.set_activity(0, stop=True)
    idle = c.get_measurements()[0]
    assert idle.voltage_V == 5.0
    assert idle.current_mA == 0.0


def test_battery_db_roundtrip():
    from app.protocol.models import BatteryDbEntry

    c = Alc8xxxClient(Alc8xxxSimulator(), channel_count=4, has_logger=True)
    entry = BatteryDbEntry(slot=2, name="TestAkku", battery_type=0x01, cells=3, capacity_mAh=1500, full_factor=99)
    out = c.set_battery_db(entry)
    assert out.name == "TestAkku"
    assert out.full_factor == 250
    assert out.cells == 3


def test_battery_db_roundtrip_low_current():
    """ALC 8xxx/3000 Classic Id-first must keep small presets intact."""
    from app.protocol.alc8xxx import models as wire
    from app.protocol.models import BatteryDbEntry

    entry = BatteryDbEntry(
        slot=8,
        name="SANYO700",
        battery_type=0x00,
        cells=2,
        capacity_mAh=700.0,
        discharge_mA=233.0,
        charge_mA=233.0,
        forming_mA=50.0,
    )
    decoded = wire.decode_battery_db(wire.encode_battery_db(entry))
    assert decoded.capacity_mAh == 700.0
    assert decoded.discharge_mA == 233.0
    assert decoded.charge_mA == 233.0
    assert decoded.forming_mA == 50.0


def test_8000_no_logger():
    c = Alc8xxxClient(
        Alc8xxxSimulator(channel_count=3, has_logger=False, ident_prefix=IDENT_8000_PLUS),
        channel_count=3,
        has_logger=False,
    )
    try:
        c.read_logger(0)
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass
