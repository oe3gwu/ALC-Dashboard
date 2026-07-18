"""In-Memory-Zustand für den ALC-7000-Simulator (Kanal-/Messlogik)."""

from __future__ import annotations

import math
import time

from app.protocol.alc7000.mapping import (
    AKKU7000_BLEI,
    AKKU7000_NICD_NIMH,
    KSTAT_AKTIV,
    KSTAT_INAKTIV,
    PROG7000_ENTLADEN,
    PROG7000_ENTLADEN_LADEN,
    PROG7000_LADEN,
    PROG7000_TEST,
    STRR_ENTLADEN,
    STRR_LADEN,
    STRR_UNDEF,
    program_from_7000,
)
from app.protocol.models import LoggerSample
from app.services.sim_physics import (
    PROG_DISCHARGE,
    PROG_DISCHARGE_CHARGE,
    PROG_TEST,
    idle_measurement,
    simulate_channel,
)

CHANNEL_COUNT = 4


class ChannelState:
    __slots__ = (
        "program",
        "cells",
        "charge_A",
        "discharge_A",
        "capacity_Ah",
        "akku_typ",
        "kan_status",
        "ak_status",
        "i_richtg",
        "t0",
        "logger",
    )

    def __init__(self) -> None:
        self.program = PROG7000_LADEN
        self.cells = 4
        self.charge_A = 0.5
        self.discharge_A = 0.25
        self.capacity_Ah = 2.0
        self.akku_typ = AKKU7000_NICD_NIMH
        self.kan_status = KSTAT_INAKTIV
        self.ak_status = 1  # Akku ang.
        self.i_richtg = STRR_UNDEF
        self.t0 = 0.0
        self.logger: list[LoggerSample] = []


class Alc7000Engine:
    def __init__(self) -> None:
        self.channels = [ChannelState() for _ in range(CHANNEL_COUNT)]
        self.ident = "ALC7000"
        self.version = "Sim 1.0"
        self.serial_number = "SIM-ALC7000"
        self.firmware = "ALC7000 Sim 1.0"

    def measure(self, ch: int) -> tuple[int, int, int]:
        """Rohwerte wie Gerät: U*1000, I*1000, C*100."""
        st = self.channels[ch]
        cells = max(1, st.cells)
        if st.kan_status != KSTAT_AKTIV:
            v, _i, _c = idle_measurement(cells)
            return int(round(v * 1000)), 0, 0

        dash_prog = program_from_7000(st.program)
        elapsed = max(0.0, time.time() - st.t0)
        v, i_mA, cap_mAh, _stage = simulate_channel(
            dash_prog,
            cells,
            st.charge_A * 1000.0,
            st.discharge_A * 1000.0,
            st.capacity_Ah * 1000.0,
            elapsed,
        )

        # Direction for UI (negative current on discharge)
        phase = dash_prog
        if dash_prog == PROG_DISCHARGE_CHARGE:
            phase = PROG_DISCHARGE if elapsed < 600 else 0x01
        if phase in (PROG_DISCHARGE, PROG_TEST):
            st.i_richtg = STRR_ENTLADEN
        else:
            st.i_richtg = STRR_LADEN

        i_A = abs(i_mA) / 1000.0
        cap_Ah = abs(cap_mAh) / 1000.0
        return int(round(v * 1000)), int(round(i_A * 1000)), int(round(cap_Ah * 100))

    def activate(self, ch: int, aktiv: int) -> None:
        st = self.channels[ch]
        if aktiv:
            st.kan_status = KSTAT_AKTIV
            st.t0 = time.time()
            if st.program in (PROG7000_ENTLADEN, PROG7000_ENTLADEN_LADEN, PROG7000_TEST):
                st.i_richtg = STRR_ENTLADEN
            else:
                st.i_richtg = STRR_LADEN
            self._seed_logger(ch)
        else:
            st.kan_status = KSTAT_INAKTIV
            st.i_richtg = STRR_UNDEF

    def _seed_logger(self, ch: int) -> None:
        st = self.channels[ch]
        samples: list[LoggerSample] = []
        cells = max(1, st.cells)
        v_cell = 2.0 if st.akku_typ == AKKU7000_BLEI else 1.2
        base = v_cell * cells
        for n in range(40):
            t = n * 2.0
            samples.append(
                LoggerSample(
                    voltage_V=round(base + 0.01 * n, 3),
                    current_mA=round(st.charge_A * 1000 * (0.95 + 0.05 * math.sin(t)), 1),
                    capacity_mAh=round(st.charge_A * 1000 * t / 36.0, 1),
                )
            )
        st.logger = samples
