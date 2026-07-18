"""Constants for ALC 5000 Mobile (ChargeEasy Teil 2, Ident j)."""

from __future__ import annotations

BAUDRATE = 38400

# PDF p.4 / Journal p.46
IDENT_5000_FW2 = "j"  # ALC 5000 mobile, firmware > 2.00
IDENT_5000_LEGACY = "f"  # ALC 5000 mobile, firmware < 2.00 — unsupported

# Project assumption: 2 channels (PDF: printed channel − 1; range 00h–03h)
CHANNEL_COUNT = 2

FLAG_ACTIVATOR = 0x01  # PDF p.3 — used by 5000 Mobile
FLAG_TEMP_HINT = 0x02

FULL_FACTOR_OFF = 0xFA  # 250 — PDF: FAh = aus
INVALID_MEASURE = 0xFFFF
NO_TEMP_SENSOR = 0xABE0
TEMP_NEG_OFFSET = 0x9C40
SAMPLES_PER_BLOCK = 100
MAX_LOGGER_BLOCK = 649
DB_SLOTS = 40

# A-command start codes (PDF p.3) — stop is always 0x01
A_STOP = 0x01
PROG_TO_A_START: dict[int, int] = {
    0x01: 0x00,  # Laden
    0x02: 0x02,  # Entladen
    0x03: 0x04,  # Entladen/Laden
    0x04: 0x06,  # Test
    0x05: 0x08,  # Wartung
    0x06: 0x0A,  # Formieren
    0x07: 0x0C,  # Zyklen
    0x08: 0x0E,  # Auffrischen
}

BATTERY_TYPE_IDS = (0x00, 0x01, 0x02, 0x03, 0x04, 0x05)
