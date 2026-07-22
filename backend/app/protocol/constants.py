"""ALC 8500-2 serial protocol constants (ELV manual ch. 18 + CP 3.x)."""

from __future__ import annotations

STX = 0x02
ETX = 0x03
ESC = 0x05

ESCAPE_MAP = {
    STX: bytes([ESC, 0x12]),
    ETX: bytes([ESC, 0x13]),
    ESC: bytes([ESC, 0x15]),
}
UNESCAPE_MAP = {
    0x12: STX,
    0x13: ETX,
    0x15: ESC,
}

BAUDRATE = 38400
BYTESIZE = 8
PARITY = "E"
STOPBITS = 1

# Battery chemistry (protocol byte) — base manual + CP 3.x aliases
BATTERY_TYPES: dict[int, str] = {
    0x00: "NiCd",
    0x01: "NiMH",
    0x02: "Li-4.1",      # classic Li-Ion / Li-4.1
    0x03: "Li-4.2",      # classic LiPo / Li-4.2
    0x04: "Pb",
    0x05: "LiFePO4",
    0x06: "Li-4.35",     # CP 3.x extension (verify on device)
    0x07: "NiZn",        # CP 3.x extension
    0x08: "AGM/CA",      # CP 3.x extension
    0xFF: "—",
}

BATTERY_TYPE_BY_NAME: dict[str, int] = {v: k for k, v in BATTERY_TYPES.items() if k != 0xFF}
# Aliases for ChargeProfessional naming
BATTERY_TYPE_BY_NAME.update(
    {
        "Li-Ion": 0x02,
        "LiIon": 0x02,
        "LiPo": 0x03,
        "Li-Pol": 0x03,
        "LiPol": 0x03,
        "LiFePo4": 0x05,
        "LiFePo": 0x05,
        "AGM": 0x08,
        "CA": 0x08,
    }
)

PROGRAMS: dict[int, str] = {
    0x00: "Keine",
    0x01: "Laden",
    0x02: "Entladen",
    0x03: "Entladen–Laden",
    0x04: "Test",
    0x05: "Wartung",
    0x06: "Formieren",
    0x07: "Zyklen",
    0x08: "Auffrischen",
}

PROGRAM_BY_NAME: dict[str, int] = {v: k for k, v in PROGRAMS.items()}
PROGRAM_BY_NAME.update(
    {
        "Charge": 0x01,
        "Discharge": 0x02,
        "Discharge/Charge": 0x03,
        "Maintain": 0x05,
        "Forming": 0x06,
        "Cycle": 0x07,
        "Refresh": 0x08,
    }
)

# Formieren / Zyklen / Auffrischen — Gerät (FW 2.08) NAKs diese Programme außer bei Ni-Chemie
NI_FAMILY_BATTERY_TYPES = frozenset({0x00, 0x01, 0x07})  # NiCd, NiMH, NiZn
NI_ONLY_PROGRAMS = frozenset({0x06, 0x07, 0x08})


def program_compatible(battery_type: int, program: int) -> bool:
    """False when the device would NAK this chemistry/program pair."""
    if program in NI_ONLY_PROGRAMS and battery_type not in NI_FAMILY_BATTERY_TYPES:
        return False
    return True


def program_incompatible_message(battery_type: int, program: int) -> str | None:
    if program_compatible(battery_type, program):
        return None
    bt = BATTERY_TYPES.get(battery_type, f"0x{battery_type:02X}")
    prog = PROGRAMS.get(program, f"0x{program:02X}")
    return (
        f"Programm „{prog}“ ist für Akkutyp {bt} nicht verfügbar "
        f"(nur NiCd/NiMH/NiZn). Bitte anderes Programm wählen."
    )

# Channel stage ranges (manual table)
STAGE_IDLE = "Leerlauf"
STAGE_PAUSE = "Pause/Warten"
STAGE_DISCHARGE = "Entladen"
STAGE_CHARGE = "Laden"
STAGE_TRICKLE = "Erhaltungsladung"
STAGE_DISCHARGE_DONE = "Entladen beendet"
STAGE_EMERGENCY = "Notabschaltung"


def stage_from_byte(value: int) -> str:
    if 0x00 <= value <= 0x0A:
        return STAGE_IDLE
    if 0x0B <= value <= 0x2D:
        return STAGE_PAUSE
    if 0x2E <= value <= 0x37:
        return STAGE_DISCHARGE
    if 0x38 <= value <= 0x6E:
        return STAGE_CHARGE
    if 0x6F <= value <= 0xA0:
        return STAGE_TRICKLE
    if 0xA1 <= value <= 0xC8:
        return STAGE_DISCHARGE_DONE
    return STAGE_EMERGENCY


FLAG_ACTIVATOR = 0x01

INVALID_MEASURE = 0xFFFF
NO_TEMP_SENSOR = 0xABE0
TEMP_NEG_OFFSET = 0x9C40

MAX_LOGGER_BLOCKS = 650
SAMPLES_PER_BLOCK = 100
DB_SLOTS = 40
DB_SLOT_MANUAL = 0x28  # 40+ = not from database
