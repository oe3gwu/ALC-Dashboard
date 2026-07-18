"""Canonical simulator measurement criteria for all ALC device simulators.

Wall-clock processes are accelerated by TIME_SCALE (×10) and each phase is
capped so GUI workflows finish in a few minutes.
"""

from __future__ import annotations

import math
from typing import Sequence

# Program bytes as on 8500 USB family
PROG_NONE = 0x00
PROG_CHARGE = 0x01
PROG_DISCHARGE = 0x02
PROG_DISCHARGE_CHARGE = 0x03
PROG_TEST = 0x04
PROG_MAINTAIN = 0x05
PROG_FORMING = 0x06
PROG_CYCLE = 0x07
PROG_REFRESH = 0x08

STAGE_IDLE = 0x00
STAGE_DISCHARGE = 0x32
STAGE_CHARGE = 0x40
STAGE_TRICKLE = 0x80

# Wall time vs. “device” time; phases also capped for UI testing
TIME_SCALE = 10.0
MAX_PHASE_WALL_S = 120.0
MIN_PHASE_WALL_S = 20.0
TRICKLE_WALL_S = 15.0

# Per-cell voltages: (idle, charge_end, discharge_cut)
_CHEM: dict[int, tuple[float, float, float]] = {
    0x00: (1.25, 1.45, 1.00),  # NiCd
    0x01: (1.25, 1.45, 1.00),  # NiMH
    0x02: (3.70, 4.10, 3.00),  # Li-4.1
    0x03: (3.70, 4.20, 3.00),  # Li-4.2
    0x04: (2.10, 2.40, 1.80),  # Pb
    0x05: (3.20, 3.60, 2.50),  # LiFePO4
    0x06: (3.70, 4.35, 3.00),  # Li-4.35
    0x07: (1.60, 1.90, 1.20),  # NiZn
    0x08: (2.10, 2.45, 1.80),  # AGM/CA
}


def idle_voltage(cells: int, battery_type: int = 0x01) -> float:
    """Open-circuit-ish idle voltage when no process is running."""
    v_cell, _, _ = _CHEM.get(int(battery_type), _CHEM[0x01])
    return v_cell * max(int(cells), 1)


def idle_measurement(cells: int, battery_type: int = 0x01) -> tuple[float, float, float]:
    """Return (voltage_V, current_mA, capacity_mAh) for idle channels."""
    return idle_voltage(cells, battery_type), 0.0, 0.0


def initial_stage(program: int) -> int:
    """Stage byte when a process is started."""
    if program in (PROG_DISCHARGE, PROG_DISCHARGE_CHARGE, PROG_TEST, PROG_CYCLE, PROG_REFRESH):
        return STAGE_DISCHARGE
    if program == PROG_NONE:
        return STAGE_IDLE
    if program == PROG_MAINTAIN:
        return STAGE_TRICKLE
    return STAGE_CHARGE


def _noise(elapsed: float, amp_v: float = 0.004) -> float:
    return amp_v * math.sin(elapsed * 2.7)


def _phase_duration_wall(capacity_mAh: float, current_mA: float) -> float:
    i = max(float(current_mA), 1.0)
    natural = (max(float(capacity_mAh), 1.0) / i) * 3600.0 / TIME_SCALE
    return max(MIN_PHASE_WALL_S, min(MAX_PHASE_WALL_S, natural))


def _chem_pack(cells: int, battery_type: int) -> tuple[float, float, float]:
    idle_c, end_c, cut_c = _CHEM.get(int(battery_type), _CHEM[0x01])
    n = max(int(cells), 1)
    return idle_c * n, end_c * n, cut_c * n


def _program_phases(
    program: int,
    capacity_mAh: float,
    charge_mA: float,
    discharge_mA: float,
) -> list[tuple[str, float, int]]:
    """List of (kind, wall_duration_s, stage_byte)."""
    t_chg = _phase_duration_wall(capacity_mAh, charge_mA)
    t_dis = _phase_duration_wall(capacity_mAh, discharge_mA)
    prog = int(program)

    if prog == PROG_CHARGE:
        return [("charge", t_chg, STAGE_CHARGE), ("trickle", TRICKLE_WALL_S, STAGE_TRICKLE)]
    if prog == PROG_DISCHARGE:
        return [("discharge", t_dis, STAGE_DISCHARGE)]
    if prog == PROG_DISCHARGE_CHARGE:
        return [
            ("discharge", t_dis, STAGE_DISCHARGE),
            ("charge", t_chg, STAGE_CHARGE),
            ("trickle", TRICKLE_WALL_S, STAGE_TRICKLE),
        ]
    if prog == PROG_TEST:
        return [("discharge", min(t_dis, 60.0), STAGE_DISCHARGE)]
    if prog == PROG_MAINTAIN:
        return [("trickle", max(TRICKLE_WALL_S, min(45.0, t_chg * 0.4)), STAGE_TRICKLE)]
    if prog == PROG_FORMING:
        return [("charge", t_chg, STAGE_CHARGE), ("trickle", TRICKLE_WALL_S, STAGE_TRICKLE)]
    if prog in (PROG_CYCLE, PROG_REFRESH):
        return [
            ("discharge", t_dis * 0.7, STAGE_DISCHARGE),
            ("charge", t_chg * 0.7, STAGE_CHARGE),
            ("trickle", TRICKLE_WALL_S, STAGE_TRICKLE),
        ]
    return []


def _full_factor_scale(full_factor: int) -> float:
    """250 (and invalid) = feature off → 100 % of nominal capacity."""
    ff = int(full_factor)
    if ff <= 0 or ff >= 250:
        return 1.0
    return max(1, min(150, ff)) / 100.0


def _eval_phase(
    kind: str,
    progress: float,
    cells: int,
    battery_type: int,
    charge_mA: float,
    discharge_mA: float,
    capacity_mAh: float,
    full_factor: int,
    elapsed_wall: float,
) -> tuple[float, float, float]:
    """progress in [0, 1] within the current phase."""
    p = max(0.0, min(1.0, progress))
    v_idle, v_end, v_cut = _chem_pack(cells, battery_type)
    target = max(float(capacity_mAh), 1.0) * _full_factor_scale(full_factor)
    n = _noise(elapsed_wall)

    if kind == "discharge":
        v = v_idle + 0.03 * max(cells, 1) - (v_idle + 0.03 * max(cells, 1) - v_cut) * (0.15 + 0.85 * p) + n
        i = max(0.0, float(discharge_mA) * (0.96 + 0.04 * math.sin(elapsed_wall / 25)))
        cap = target * p
        return v, i, cap

    if kind == "charge":
        # CC (~70%) then CV taper
        if p < 0.7:
            frac = p / 0.7
            v = v_idle - 0.04 * max(cells, 1) + (v_end - (v_idle - 0.04 * max(cells, 1))) * (0.2 + 0.75 * frac) + n
            i = max(0.0, float(charge_mA) * (0.97 + 0.03 * math.sin(elapsed_wall / 30)))
        else:
            frac = (p - 0.7) / 0.3
            v = v_end - 0.02 * max(cells, 1) * (1.0 - frac) + n * 0.5
            i = max(0.0, float(charge_mA) * (1.0 - 0.85 * frac))
        cap = target * p
        return v, i, cap

    # trickle / maintain
    v = v_end - 0.03 * max(cells, 1) + 0.02 * max(cells, 1) * math.sin(elapsed_wall / 18) + n * 0.3
    i = max(0.0, min(float(charge_mA) * 0.08, 80.0) * (0.9 + 0.1 * math.sin(elapsed_wall / 12)))
    cap = target
    return v, i, cap


def simulate_channel(
    program: int,
    cells: int,
    charge_mA: float,
    discharge_mA: float,
    capacity_mAh: float,
    elapsed: float,
    battery_type: int = 0x01,
    full_factor: int = 100,
) -> tuple[float, float, float, int, bool]:
    """Return (voltage_V, current_mA, capacity_mAh, stage_byte, finished)."""
    cells = max(int(cells), 1)
    prog = int(program)
    t = max(0.0, float(elapsed))

    if prog == PROG_NONE:
        v, i, cap = idle_measurement(cells, battery_type)
        return v, i, cap, STAGE_IDLE, False

    phases = _program_phases(prog, capacity_mAh, charge_mA, discharge_mA)
    if not phases:
        v, i, cap = idle_measurement(cells, battery_type)
        return v, i, cap, STAGE_IDLE, True

    cursor = 0.0
    for kind, dur, stage in phases:
        dur = max(dur, 1.0)
        if t < cursor + dur:
            progress = (t - cursor) / dur
            v, i, cap = _eval_phase(
                kind,
                progress,
                cells,
                battery_type,
                charge_mA,
                discharge_mA,
                capacity_mAh,
                full_factor,
                t,
            )
            return v, i, cap, stage, False
        cursor += dur

    # Completed — resting voltage, capacity at nominal target
    _v_idle, v_end, _cut = _chem_pack(cells, battery_type)
    target = max(float(capacity_mAh), 1.0) * _full_factor_scale(full_factor)
    return v_end * 0.98, 0.0, target, STAGE_IDLE, True


def clamp_process_currents(device_model: str, channel: int, charge_mA: float, discharge_mA: float) -> tuple[float, float]:
    """Model/channel current limits used by simulators on param write."""
    ch = max(0, int(channel))
    model = device_model or ""
    if model == "alc8500_2_expert":
        max_mA = 5000.0 if ch < 2 else 1000.0
    elif model in ("alc8000", "alc8500_expert"):
        max_mA = 5000.0 if ch < 2 else 1000.0
    elif model == "alc5000_mobile":
        max_mA = 2500.0
    elif model == "alc3000_pc":
        max_mA = 3000.0
    elif model == "alc7000_expert":
        max_mA = 5000.0
    else:
        max_mA = 5000.0
    return min(max(0.0, float(charge_mA)), max_mA), min(max(0.0, float(discharge_mA)), max_mA)


def clamp_battery_type(battery_type: int, allowed: Sequence[int]) -> int:
    bt = int(battery_type)
    if not allowed:
        return bt
    if bt in allowed:
        return bt
    return int(allowed[0])
