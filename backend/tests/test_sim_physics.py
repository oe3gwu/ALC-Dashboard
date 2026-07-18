"""Canonical simulator physics (chemistry, ×10, phases, finished)."""

from __future__ import annotations

import random

from app.protocol.units import temp_from_digits, temp_to_digits
from app.services.sim_physics import (
    MAX_PHASE_WALL_S,
    PROG_CHARGE,
    PROG_DISCHARGE,
    PROG_DISCHARGE_CHARGE,
    PROG_NONE,
    STAGE_CHARGE,
    STAGE_DISCHARGE,
    STAGE_IDLE,
    TIME_SCALE,
    SimTemperatures,
    clamp_battery_type,
    clamp_process_currents,
    idle_measurement,
    idle_voltage,
    initial_stage,
    simulate_channel,
)


def test_idle_four_cells_nimh():
    assert idle_voltage(4) == 5.0
    v, i, c = idle_measurement(4)
    assert (v, i, c) == (5.0, 0.0, 0.0)


def test_idle_chemistry_li():
    # Li-4.2: 3.7 V × 2
    assert abs(idle_voltage(2, battery_type=0x03) - 7.4) < 1e-9


def test_charge_phase_and_finish_within_cap():
    v, i, cap, stage, finished = simulate_channel(
        program=PROG_CHARGE,
        cells=4,
        charge_mA=500,
        discharge_mA=250,
        capacity_mAh=2000,
        elapsed=60,
        battery_type=0x01,
        full_factor=100,
    )
    assert v > 0
    assert i > 0
    assert cap > 0
    assert stage == STAGE_CHARGE
    assert finished is False

    # Past max phase + trickle → finished
    v2, i2, _cap2, stage2, finished2 = simulate_channel(
        program=PROG_CHARGE,
        cells=4,
        charge_mA=500,
        discharge_mA=250,
        capacity_mAh=2000,
        elapsed=MAX_PHASE_WALL_S + 30,
        battery_type=0x01,
    )
    assert finished2 is True
    assert stage2 == STAGE_IDLE
    assert i2 == 0.0
    # Charge-end pack voltage roughly 1.45 × 4
    assert 5.0 < v2 < 6.0


def test_discharge_charge_switches_phase():
    # Early: discharge
    _v, _i, _c, stage_d, fin_d = simulate_channel(
        program=PROG_DISCHARGE_CHARGE,
        cells=4,
        charge_mA=1000,
        discharge_mA=1000,
        capacity_mAh=500,
        elapsed=5,
    )
    assert stage_d == STAGE_DISCHARGE
    assert fin_d is False

    # After first phase duration (capped), should be charging
    _v2, _i2, _c2, stage_c, fin_c = simulate_channel(
        program=PROG_DISCHARGE_CHARGE,
        cells=4,
        charge_mA=1000,
        discharge_mA=1000,
        capacity_mAh=500,
        elapsed=MAX_PHASE_WALL_S + 5,
    )
    assert stage_c == STAGE_CHARGE
    assert fin_c is False


def test_idle_program_unchanged():
    v, i, cap, stage, finished = simulate_channel(
        program=PROG_NONE,
        cells=4,
        charge_mA=500,
        discharge_mA=250,
        capacity_mAh=2000,
        elapsed=999,
    )
    assert (v, i, cap) == (5.0, 0.0, 0.0)
    assert stage == STAGE_IDLE
    assert finished is False


def test_initial_stage_discharge():
    assert initial_stage(PROG_DISCHARGE) == STAGE_DISCHARGE


def test_time_scale_constant():
    assert TIME_SCALE == 10.0


def test_clamp_currents_8500_2():
    chg, dis = clamp_process_currents("alc8500_2_expert", 3, 5000, 5000)
    assert chg == 1000.0
    assert dis == 1000.0
    chg0, _ = clamp_process_currents("alc8500_2_expert", 0, 6000, 100)
    assert chg0 == 5000.0


def test_clamp_battery_type():
    assert clamp_battery_type(0x07, (0x00, 0x01, 0x04)) == 0x00
    assert clamp_battery_type(0x01, (0x00, 0x01, 0x04)) == 0x01


def test_temp_to_digits_roundtrip():
    assert temp_to_digits(25.0) == 2500
    assert temp_to_digits(32.0) == 3200
    assert temp_to_digits(28.0) == 2800
    assert abs(temp_from_digits(temp_to_digits(25.37)) - 25.37) < 0.01


def test_sim_temperatures_heatsink_psu_step():
    rng = random.Random(1)
    temps = SimTemperatures(now=0.0, rng=rng)
    temps.sample(now=0.0)
    # Force several 5 s steps — underlying walk must leave start values
    temps.sample(now=25.0)
    assert temps._hs != SimTemperatures.BASE_HEATSINK_C or temps._psu != SimTemperatures.BASE_PSU_C
    assert abs(temps._hs - SimTemperatures.BASE_HEATSINK_C) <= SimTemperatures.BAND_C
    assert abs(temps._psu - SimTemperatures.BASE_PSU_C) <= SimTemperatures.BAND_C


def test_sim_temperatures_battery_rises_when_charging():
    temps = SimTemperatures(now=0.0, rng=random.Random(0))
    bat0, _, _ = temps.sample(charging=False, discharging=False, now=0.0)
    bat1, _, _ = temps.sample(charging=True, discharging=False, now=30.0)
    assert bat1 > bat0
