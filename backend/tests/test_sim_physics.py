"""Canonical simulator physics (8500-2 criteria)."""

from __future__ import annotations

from app.services.sim_physics import idle_measurement, idle_voltage, initial_stage, simulate_channel


def test_idle_four_cells():
    assert idle_voltage(4) == 5.0
    v, i, c = idle_measurement(4)
    assert (v, i, c) == (5.0, 0.0, 0.0)


def test_charge_phase():
    v, i, cap, stage = simulate_channel(
        program=0x01,
        cells=4,
        charge_mA=500,
        discharge_mA=250,
        capacity_mAh=2000,
        elapsed=60,
    )
    assert v > 0
    assert i > 0
    assert cap > 0
    assert stage == 0x40  # Laden


def test_initial_stage_discharge():
    assert initial_stage(0x02) == 0x32
