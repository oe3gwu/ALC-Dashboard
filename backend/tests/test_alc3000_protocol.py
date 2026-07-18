"""Roundtrip-Tests: Alc3000Client ↔ Simulator (ChargeEasy Teil 2)."""

from __future__ import annotations

from app.protocol.alc3000.client import Alc3000Client
from app.protocol.alc3000.simulator import Alc3000Simulator
from app.protocol.models import ChannelParams, DeviceParamsG


def test_idle_measurements_match_8500_2():
    c = Alc3000Client(Alc3000Simulator())
    m = c.get_measurements()
    assert len(m) == 1
    assert m[0].voltage_V == 5.0  # 1.25 V × 4 cells
    assert m[0].current_mA == 0.0
    assert m[0].capacity_mAh == 0.0


def test_params_start_stop():
    c = Alc3000Client(Alc3000Simulator())
    echoed = c.set_channel_params(
        ChannelParams(
            channel=0,
            battery_type=0x01,
            cells=4,
            capacity_mAh=2000,
            charge_mA=500,
            discharge_mA=250,
            program=0x01,
            full_factor=100,
        )
    )
    assert echoed.channel == 0
    assert echoed.full_factor == 250
    assert echoed.charge_mA == 500
    st = c.set_activity(0, stop=False)
    assert st.stage_name == "Laden"
    m = c.get_measurements()[0]
    assert m.voltage_V is not None and m.voltage_V > 0
    c.set_activity(0, stop=True)
    idle = c.get_measurements()[0]
    assert idle.voltage_V == 5.0


def test_chemistry_g_h_j():
    c = Alc3000Client(Alc3000Simulator())
    g = c.get_device_g()
    assert g.pause_min >= 0
    c.set_device_g(DeviceParamsG(pause_min=5))
    assert c.get_device_g().pause_min == 5
    h = c.get_device_h()
    assert h.charge_LiIon_mV > 0
    j = c.get_device_j()
    assert j.charge_LiFePO4_mV > 0


def test_ident_prefix():
    sim = Alc3000Simulator()
    assert sim.ident.startswith("g")
