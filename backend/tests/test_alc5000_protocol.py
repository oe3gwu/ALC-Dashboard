"""Roundtrip tests: Alc5000Client ↔ Simulator (ChargeEasy Teil 2, Ident j)."""

from __future__ import annotations

import pytest

from app.protocol.alc5000.client import Alc5000Client, UnsupportedAlc5000Error
from app.protocol.alc5000.framing import build_frame, parse_frame
from app.protocol.alc5000.models import (
    decode_channel_params,
    encode_bcd_byte,
    encode_channel_set,
    encode_rtc,
    decode_bcd_byte,
    decode_rtc,
)
from app.protocol.alc5000.simulator import Alc5000Simulator
from app.protocol.models import ChannelParams, DeviceParamsG, DeviceParamsH


def test_framing_escape_roundtrip():
    payload = bytes([0x02, 0x03, 0x05, ord("p"), 0x00])
    frame = build_frame(payload)
    assert parse_frame(frame) == payload


def test_ident_j_ok():
    c = Alc5000Client(Alc5000Simulator())
    fw = c.ensure_supported_device()
    assert fw.startswith("j")


def test_ident_f_rejected():
    sim = Alc5000Simulator()
    sim.firmware = "f1.90     "
    c = Alc5000Client(sim)
    with pytest.raises(UnsupportedAlc5000Error, match="Firmware"):
        c.ensure_supported_device()


def test_ident_g_rejected():
    sim = Alc5000Simulator()
    sim.firmware = "gALC3000  "
    c = Alc5000Client(sim)
    with pytest.raises(UnsupportedAlc5000Error, match="Gerät"):
        c.ensure_supported_device()


def test_idle_two_channels():
    c = Alc5000Client(Alc5000Simulator())
    m = c.get_measurements()
    assert len(m) == 2
    assert m[0].voltage_V == 5.0
    assert m[1].voltage_V == 5.0
    assert m[0].current_mA == 0.0


def test_params_full_factor_roundtrip():
    """assumed BE multi-byte packing."""
    c = Alc5000Client(Alc5000Simulator())
    echoed = c.set_channel_params(
        ChannelParams(
            channel=1,
            battery_type=0x01,
            cells=4,
            capacity_mAh=2000,
            charge_mA=500,
            discharge_mA=250,
            program=0x01,
            full_factor=100,
            flags=0x01,
        )
    )
    assert echoed.channel == 1
    assert echoed.full_factor == 100
    assert echoed.charge_mA == 500
    assert echoed.activator is True


def test_channel_wire_set_vs_read_layout():
    """assumed: SET = flags+ff; READ = flags+Messende+ff+stage."""
    p = ChannelParams(channel=0, cells=4, full_factor=0x64, logger_samples=42, stage=0x40)
    set_body = encode_channel_set(p)
    assert len(set_body) == 19
    assert set_body[-1] == 0x64
    decoded_set = decode_channel_params(set_body)
    assert decoded_set.full_factor == 100
    assert decoded_set.logger_samples == 0

    from app.protocol.alc5000.models import encode_channel_read

    read_body = encode_channel_read(p)
    assert len(read_body) == 22
    decoded = decode_channel_params(read_body)
    assert decoded.full_factor == 100
    assert decoded.logger_samples == 42
    assert decoded.stage == 0x40


def test_m_per_channel_and_start_stop():
    c = Alc5000Client(Alc5000Simulator())
    c.set_channel_params(
        ChannelParams(channel=0, cells=4, program=0x01, charge_mA=500, capacity_mAh=2000, full_factor=100)
    )
    st = c.set_activity(0, stop=False)
    assert st.stage_name == "Laden"
    # UI polls get_channel_params — stage must reflect running / idle
    assert c.get_channel_params(0).stage_name == "Laden"
    m = c.get_measurements()[0]
    assert m.voltage_V is not None and m.voltage_V > 0
    c.set_activity(0, stop=True)
    assert c.get_channel_params(0).stage_name == "Leerlauf"
    assert c.get_measurements()[0].voltage_V == 5.0


def test_rtc_bcd_roundtrip():
    raw = encode_rtc(59, 30, 14, 17, 7, 26)
    assert decode_bcd_byte(encode_bcd_byte(59)) == 59
    assert decode_rtc(raw) == (59, 30, 14, 17, 7, 26)
    c = Alc5000Client(Alc5000Simulator())
    c.set_rtc(10, 20, 8, 1, 1, 26)
    assert c.get_rtc() == (10, 20, 8, 1, 1, 26)


def test_chemistry_and_lowbat():
    c = Alc5000Client(Alc5000Simulator())
    g = c.get_device_g()
    assert g.pause_min >= 0
    c.set_device_g(DeviceParamsG(pause_min=5))
    assert c.get_device_g().pause_min == 5
    h = c.get_device_h()
    assert h.unused == 10500  # LowBat Speiseakku stub
    c.set_device_h(DeviceParamsH(unused=11000))
    assert c.get_device_h().unused == 11000
    assert c.get_device_j().charge_LiFePO4_mV > 0


def test_battery_db_roundtrip():
    c = Alc5000Client(Alc5000Simulator())
    from app.protocol.models import BatteryDbEntry

    entry = BatteryDbEntry(slot=3, name="TestAkku", cells=4, capacity_mAh=2500, full_factor=100)
    echoed = c.set_battery_db(entry)
    assert echoed.name == "TestAkku"
    assert echoed.full_factor == 100
    assert echoed.capacity_mAh == 2500
