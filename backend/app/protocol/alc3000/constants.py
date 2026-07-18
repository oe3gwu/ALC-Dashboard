"""Constants for ALC 3000 PC (ChargeEasy Teil 2)."""

from __future__ import annotations

BAUDRATE = 38400

# Article: NiCd…LiFePO (+ FF empty)
BATTERY_TYPE_IDS = (0x00, 0x01, 0x02, 0x03, 0x04, 0x05)

IDENT_3000 = "g"  # ALC 3000 PC, firmware > 2.00

FLAG_TEMP_SENSOR = 0x02  # bit 2^1 — 3000 uses this; activator bit unused
INVALID_MEASURE = 0xFFFF
SAMPLES_PER_BLOCK = 100
DB_SLOTS = 40
