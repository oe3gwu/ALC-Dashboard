from __future__ import annotations

from .constants import INVALID_MEASURE, NO_TEMP_SENSOR, TEMP_NEG_OFFSET


def current_to_digits(mA: float) -> int:
    """mA → protocol digits (0.1 mA/digit)."""
    return max(0, min(0xFFFF, int(round(mA * 10))))


def current_from_digits(digits: int, *, allow_invalid: bool = False) -> float | None:
    """Decode current. For live/logger samples, 0xFFFF means missing/pause."""
    if allow_invalid and digits == INVALID_MEASURE:
        return None
    return digits / 10.0


def capacity_to_digits(mAh: float) -> int:
    """mAh → protocol digits (1 mAh = 10000)."""
    return max(0, int(round(mAh * 10000)))


def capacity_from_digits(digits: int) -> float:
    return digits / 10000.0


def voltage_to_digits(V: float) -> int:
    """V → mV digits."""
    return max(0, int(round(V * 1000)))


def voltage_from_digits(digits: int) -> float | None:
    if digits == INVALID_MEASURE:
        return None
    return digits / 1000.0


def temp_from_digits(digits: int) -> float | None:
    """0.01 °C per digit; negative via offset 0x9C40; no sensor 0xABE0."""
    if digits == NO_TEMP_SENSOR or digits == INVALID_MEASURE:
        return None
    if digits >= TEMP_NEG_OFFSET:
        return (digits - TEMP_NEG_OFFSET) / 100.0 - (TEMP_NEG_OFFSET / 100.0)
    # Manual: negative values use offset 9c40h
    # Simpler interpretation used by community: signed via offset
    if digits > 0x8000:
        return (digits - 0x10000) / 100.0
    return digits / 100.0


def temp_to_digits(celsius: float) -> int:
    """°C → protocol digits (0.01 °C/digit). Negative via TEMP_NEG_OFFSET."""
    t = float(celsius)
    if t < 0:
        return max(0, min(0xFFFF, int(round(TEMP_NEG_OFFSET + t * 100.0))))
    return max(0, min(0xFFFF, int(round(t * 100.0))))


def u16(data: bytes, offset: int) -> int:
    return (data[offset] << 8) | data[offset + 1]


def u32(data: bytes, offset: int) -> int:
    return (
        (data[offset] << 24)
        | (data[offset + 1] << 16)
        | (data[offset + 2] << 8)
        | data[offset + 3]
    )


def pack_u16(value: int) -> bytes:
    value &= 0xFFFF
    return bytes([(value >> 8) & 0xFF, value & 0xFF])


def pack_u32(value: int) -> bytes:
    value &= 0xFFFFFFFF
    return bytes(
        [
            (value >> 24) & 0xFF,
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
        ]
    )
