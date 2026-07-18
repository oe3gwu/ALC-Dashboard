"""Roundtrip-Tests: Alc7000Client ↔ Simulator (Wire wie alc7t/pyALC7T)."""

from __future__ import annotations

from app.protocol.alc7000.client import Alc7000Client
from app.protocol.alc7000.framing import ACK, build_data_request, encode_byte
from app.protocol.alc7000.simulator import Alc7000Simulator
from app.protocol.models import ChannelParams


def test_encode_escape():
    assert encode_byte(0x02) == bytes([0x05, 0x12])
    assert encode_byte(0x03) == bytes([0x05, 0x13])
    assert encode_byte(0x05) == bytes([0x05, 0x15])
    assert encode_byte(0x01) == bytes([0x01])


def test_build_data_request_shape():
    frame = build_data_request("i", 0, 0, 0)
    assert frame[0] == 0x02
    assert frame[1] == ord("i")
    assert frame[-1] == 0x03


def test_ident_and_params_roundtrip():
    c = Alc7000Client(Alc7000Simulator())
    assert c.read_ident()
    assert c.read_version()
    p = ChannelParams(
        channel=0,
        battery_type=0x01,
        cells=4,
        capacity_mAh=2000,
        charge_mA=500,
        discharge_mA=250,
        program=0x01,
    )
    echoed = c.set_channel_params(p)
    assert echoed.cells == 4
    assert echoed.charge_mA == 500
    assert echoed.program == 0x01
    assert echoed.stage_name == "Leerlauf"


def test_start_stop_stage():
    c = Alc7000Client(Alc7000Simulator())
    c.set_channel_params(
        ChannelParams(channel=0, battery_type=0x01, cells=4, capacity_mAh=2000, charge_mA=500, program=0x01)
    )
    st = c.set_activity(0, stop=False)
    assert st.stage_name == "Laden"
    assert c.get_channel_params(0).stage_name == "Laden"
    m = c.get_measurements()[0]
    assert m.voltage_V and m.voltage_V > 0
    assert m.current_mA and m.current_mA > 0
    c.set_activity(0, stop=True)
    assert c.get_channel_params(0).stage_name == "Leerlauf"


def test_discharge_program_negative_current():
    c = Alc7000Client(Alc7000Simulator())
    c.set_channel_params(
        ChannelParams(channel=0, battery_type=0x04, cells=3, capacity_mAh=1200, charge_mA=300, discharge_mA=200, program=0x02)
    )
    c.set_activity(0, stop=False)
    assert c.get_channel_params(0).stage_name == "Entladen"
    m = c.get_measurements()[0]
    assert m.current_mA is not None and m.current_mA < 0


def test_write_ack():
    sim = Alc7000Simulator()
    assert sim.com_data("F", 1, 0, 1, True) == ACK
