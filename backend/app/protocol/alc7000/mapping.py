"""Dashboard-↔ALC7000-Werte (Programme / Akkutypen)."""

from __future__ import annotations

# pyALC7T / alc7t Programm-IDs
PROG7000_LADEN = 0
PROG7000_ENTLADEN = 1
PROG7000_ENTLADEN_LADEN = 2
PROG7000_TEST = 3
PROG7000_ZYKLISCH = 4
PROG7000_REFRESH = 5

# Dashboard (8500-2-ähnliche) Program-Bytes → 7000
_DASH_TO_7000: dict[int, int] = {
    0x01: PROG7000_LADEN,
    0x02: PROG7000_ENTLADEN,
    0x03: PROG7000_ENTLADEN_LADEN,
    0x04: PROG7000_TEST,
    0x07: PROG7000_ZYKLISCH,
    0x08: PROG7000_REFRESH,
}

_7000_TO_DASH: dict[int, int] = {v: k for k, v in _DASH_TO_7000.items()}

# Dashboard battery_type → 7000 (0=NiCd/NiMH, 1=Blei)
# 0x00 NiCd, 0x01 NiMH → 0; 0x04 Pb → 1
AKKU7000_NICD_NIMH = 0
AKKU7000_BLEI = 1


def program_to_7000(dash_program: int) -> int:
    return _DASH_TO_7000.get(dash_program, PROG7000_LADEN)


def program_from_7000(prog: int) -> int:
    return _7000_TO_DASH.get(prog, 0x01)


def battery_to_7000(dash_type: int) -> int:
    if dash_type == 0x04:
        return AKKU7000_BLEI
    return AKKU7000_NICD_NIMH


def battery_from_7000(akku: int, prefer_nimh: bool = True) -> int:
    if akku == AKKU7000_BLEI:
        return 0x04
    return 0x01 if prefer_nimh else 0x00


# Stage-Bytes für UI (8500 stage_from_byte)
STAGE_IDLE = 0x00
STAGE_DISCHARGE = 0x32
STAGE_CHARGE = 0x40

KSTAT_INAKTIV = 0
KSTAT_AKTIV = 1
STRR_UNDEF = 0
STRR_LADEN = 1
STRR_ENTLADEN = 2
