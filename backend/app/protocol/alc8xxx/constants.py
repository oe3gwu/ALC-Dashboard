"""Constants for ALC 8000 / 8500 Expert (ELVjournal protocol)."""

from __future__ import annotations

# Same link layer as 8500-2 USB
BAUDRATE = 38400

# Battery types documented in the article (no CP 3.x extensions)
BATTERY_TYPES: dict[int, str] = {
    0x00: "NiCd",
    0x01: "NiMH",
    0x02: "Li-Ion",
    0x03: "Li-Pol",
    0x04: "Pb",
    0xFF: "—",
}

BATTERY_TYPE_IDS = (0x00, 0x01, 0x02, 0x03, 0x04)

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

FLAG_ACTIVATOR = 0x01
INVALID_MEASURE = 0xFFFF
SAMPLES_PER_BLOCK = 100
MAX_LOGGER_BLOCKS = 650
DB_SLOTS = 40
DB_SLOT_MANUAL = 0x28

# Ident first letter (article table)
IDENT_8500 = "b"
IDENT_8000 = "c"
IDENT_8500_2 = "d"  # not used by this package
IDENT_8000_PLUS = "e"
