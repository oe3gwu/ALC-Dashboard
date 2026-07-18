"""Canonical simulator measurement criteria (ALC 8500-2 MockDevice).

All device simulators (8500-2, 8000/8500 Expert, 3000, 7000, and future
models) must use these helpers so idle/live U·I·Cap curves stay consistent.
"""

from __future__ import annotations

import math

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


def idle_voltage(cells: int) -> float:
    """Open-circuit-ish idle voltage shown when no process is running."""
    return 1.25 * max(int(cells), 1)


def idle_measurement(cells: int) -> tuple[float, float, float]:
    """Return (voltage_V, current_mA, capacity_mAh) for idle channels."""
    return idle_voltage(cells), 0.0, 0.0


def initial_stage(program: int) -> int:
    """Stage byte when a process is started."""
    if program in (PROG_DISCHARGE, PROG_DISCHARGE_CHARGE, PROG_TEST):
        return STAGE_DISCHARGE
    if program == PROG_NONE:
        return STAGE_IDLE
    return STAGE_CHARGE


def _noise(elapsed: float, amp_v: float = 0.005) -> float:
    return amp_v * math.sin(elapsed * 2.7)


def simulate_channel(
    program: int,
    cells: int,
    charge_mA: float,
    discharge_mA: float,
    capacity_mAh: float,
    elapsed: float,
) -> tuple[float, float, float, int]:
    """Return (voltage_V, current_mA, capacity_mAh, stage_byte) for a running process."""
    cells = max(int(cells), 1)
    v_nom = 1.2 * cells
    prog = int(program)
    t = max(0.0, float(elapsed))

    # Entladen–Laden: first 10 min discharge, then charge
    if prog == PROG_DISCHARGE_CHARGE:
        if t < 600:
            prog_phase = PROG_DISCHARGE
        else:
            prog_phase = PROG_CHARGE
            t = t - 600
    else:
        prog_phase = prog

    if prog_phase in (PROG_DISCHARGE, PROG_TEST):
        drop = min(0.35 * cells, t / 800)
        v = v_nom + 0.05 * cells - drop + _noise(t)
        i = max(0.0, float(discharge_mA) * (0.95 + 0.02 * math.sin(t / 40)))
        cap = float(capacity_mAh) * min(1.0, t / 3600)
        stage = STAGE_DISCHARGE
    elif prog_phase in (PROG_CHARGE, PROG_MAINTAIN, PROG_FORMING, PROG_CYCLE, PROG_REFRESH):
        rise = min(0.35 * cells, t / 700)
        taper = min(0.12, t / 5000)
        v = v_nom - 0.05 * cells + rise + _noise(t)
        i = max(0.0, float(charge_mA) * (1.0 - taper))
        cap = float(capacity_mAh) * min(1.0, t / 3600)
        stage = STAGE_TRICKLE if prog_phase == PROG_MAINTAIN else STAGE_CHARGE
    else:
        v, i, cap = idle_measurement(cells)
        stage = STAGE_IDLE

    return v, i, cap, stage
