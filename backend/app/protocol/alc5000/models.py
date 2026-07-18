"""Wire encode/decode for ALC 5000 Mobile (ChargeEasy Teil 2, Ident j).

Channel `p`/`P` includes Vollfaktor. Read layout: FLAGS + Messende(2) + Vollfaktor
(PDF p.2–4). Multi-byte values: big-endian assumed (not stated in PDF).
"""

from __future__ import annotations

from app.protocol.models import BatteryDbEntry, ChannelParams
from app.protocol.units import (
    capacity_from_digits,
    capacity_to_digits,
    current_from_digits,
    current_to_digits,
    pack_u16,
    pack_u32,
    u16,
    u32,
)

# P SET after command: 19 bytes (flags + full_factor)
# p READ after command: flags + Messende(2) + Vollfaktor (+ optional stage not in PDF list)


def encode_channel_set(p: ChannelParams) -> bytes:
    """P payload after command letter (includes Vollfaktor, no Messende)."""
    return (
        bytes(
            [
                p.channel & 0xFF,
                p.battery_slot & 0xFF,
                p.battery_type & 0xFF,
                p.cells & 0xFF,
            ]
        )
        + pack_u16(current_to_digits(p.discharge_mA))
        + pack_u16(current_to_digits(p.charge_mA))
        + pack_u32(capacity_to_digits(p.capacity_mAh))
        + bytes([p.program & 0xFF])
        + pack_u16(current_to_digits(p.forming_mA))
        + pack_u16(p.pause_s & 0xFFFF)
        + bytes([p.flags & 0xFF, p.full_factor & 0xFF])
    )


def encode_channel_read(p: ChannelParams) -> bytes:
    """p/P reply body: FLAGS + Messende + Vollfaktor + stage (dashboard/sim extension)."""
    core = encode_channel_set(p)
    # strip trailing Vollfaktor, insert Messende, append Vollfaktor + stage
    without_ff = core[:-1]
    return (
        without_ff
        + pack_u16(p.logger_samples & 0xFFFF)
        + bytes([p.full_factor & 0xFF, p.stage & 0xFF])
    )


def decode_channel_params(data: bytes) -> ChannelParams:
    """Decode p/P body after command letter.

    SET (19 B): … flags, full_factor
    READ (≥21 B): … flags, Messende(2), full_factor [, stage]
    """
    if len(data) < 19:
        raise ValueError(f"Kanalparameter zu kurz: {len(data)} Bytes")
    o = 0
    ch = data[o]
    o += 1
    slot = data[o]
    o += 1
    btype = data[o]
    o += 1
    cells = data[o]
    o += 1
    Id = u16(data, o)
    o += 2
    Ic = u16(data, o)
    o += 2
    cap = u32(data, o)
    o += 4
    prog = data[o]
    o += 1
    If = u16(data, o)
    o += 2
    pause = u16(data, o)
    o += 2
    flags = data[o]
    o += 1

    logger = 0
    full = 250
    stage = 0
    remaining = len(data) - o
    if remaining >= 3:
        # READ: Messende + Vollfaktor [+ stage]
        logger = u16(data, o)
        o += 2
        full = data[o]
        o += 1
        if len(data) > o:
            stage = data[o]
    elif remaining >= 1:
        # SET echo / write payload: Vollfaktor only
        full = data[o]
    return ChannelParams(
        channel=ch,
        battery_slot=slot,
        battery_type=btype,
        cells=cells,
        discharge_mA=current_from_digits(Id) or 0.0,
        charge_mA=current_from_digits(Ic) or 0.0,
        capacity_mAh=capacity_from_digits(cap),
        program=prog,
        forming_mA=current_from_digits(If) or 0.0,
        pause_s=pause,
        flags=flags,
        full_factor=full,
        logger_samples=logger,
        stage=stage,
    )


def encode_battery_db(entry: BatteryDbEntry, function_enable: int = 0xFF) -> bytes:
    """D payload: Cap before currents; FLAGS + Vollfaktor + Funktionsfreigabe (PDF p.4)."""
    name = entry.name.encode("latin-1", errors="replace")[:9]
    name = name.ljust(9, b"\x00")
    return (
        bytes([entry.slot & 0xFF])
        + name
        + bytes([entry.battery_type & 0xFF, entry.cells & 0xFF])
        + pack_u32(capacity_to_digits(entry.capacity_mAh))
        + pack_u16(current_to_digits(entry.discharge_mA))
        + pack_u16(current_to_digits(entry.charge_mA))
        + pack_u16(entry.pause_s)
        + bytes([entry.flags & 0xFF, entry.full_factor & 0xFF, function_enable & 0xFF])
    )


def decode_battery_db(data: bytes) -> BatteryDbEntry:
    """Decode d/D body. Vollfaktor may be omitted on some read replies (PDF open point)."""
    # Minimum without Vollfaktor: slot+name+type+cells+cap+Id+Ic+pause+flags = 23
    if len(data) < 23:
        raise ValueError("Datenbank-Eintrag zu kurz")
    slot = data[0]
    name = data[1:10].split(b"\x00", 1)[0].decode("latin-1", errors="replace").strip()
    o = 10
    btype = data[o]
    o += 1
    cells = data[o]
    o += 1
    cap = u32(data, o)
    o += 4
    Id = u16(data, o)
    o += 2
    Ic = u16(data, o)
    o += 2
    pause = u16(data, o)
    o += 2
    flags = data[o] if len(data) > o else 0
    o += 1
    full = data[o] if len(data) > o else 250
    return BatteryDbEntry(
        slot=slot,
        name=name,
        battery_type=btype,
        cells=cells,
        capacity_mAh=capacity_from_digits(cap),
        discharge_mA=current_from_digits(Id) or 0.0,
        charge_mA=current_from_digits(Ic) or 0.0,
        pause_s=pause,
        forming_mA=0.0,
        flags=flags,
        full_factor=full,
    )


def encode_bcd_byte(value: int) -> int:
    """Pack 0–99 as one BCD byte."""
    v = max(0, min(99, int(value)))
    return ((v // 10) << 4) | (v % 10)


def decode_bcd_byte(b: int) -> int:
    return ((b >> 4) & 0x0F) * 10 + (b & 0x0F)


def encode_rtc(sec: int, minute: int, hour: int, day: int, month: int, year: int) -> bytes:
    """C payload: 6× BCD (sec…year). PDF p.7 / Journal p.49."""
    return bytes(
        [
            encode_bcd_byte(sec),
            encode_bcd_byte(minute),
            encode_bcd_byte(hour),
            encode_bcd_byte(day),
            encode_bcd_byte(month),
            encode_bcd_byte(year % 100),
        ]
    )


def decode_rtc(data: bytes) -> tuple[int, int, int, int, int, int]:
    if len(data) < 6:
        raise ValueError("RTC-Daten zu kurz")
    return (
        decode_bcd_byte(data[0]),
        decode_bcd_byte(data[1]),
        decode_bcd_byte(data[2]),
        decode_bcd_byte(data[3]),
        decode_bcd_byte(data[4]),
        decode_bcd_byte(data[5]),
    )


def parse_u_payload(data: bytes) -> tuple[str, str]:
    """u body after command: FW(10) + pad(2) + SN(10). Returns (firmware, serial)."""
    if len(data) < 10:
        raise ValueError("u-Antwort zu kurz")
    fw = data[0:10].split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
    sn = ""
    if len(data) >= 22:
        sn = data[12:22].split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
    return fw, sn
