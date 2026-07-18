"""Wire encode/decode for ALC 8000 / 8500 Expert (no full_factor byte)."""

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

# SET payload after 'P': 18 bytes (no full_factor)
# ch slot type cells Id(2) Ic(2) Cap(4) prog If(2) pause(2) flags
# READ adds logger(2) + stage(1)


def encode_channel_set(p: ChannelParams) -> bytes:
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
        + bytes([p.flags & 0xFF])
    )


def decode_channel_params(data: bytes) -> ChannelParams:
    """Decode p/P body after command letter. full_factor always 250 (off)."""
    if len(data) < 18:
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
    stage = 0
    if len(data) >= o + 2:
        logger = u16(data, o)
        o += 2
    if len(data) > o:
        stage = data[o]
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
        full_factor=250,
        logger_samples=logger,
        stage=stage,
    )


def encode_battery_db(entry: BatteryDbEntry) -> bytes:
    """DB entry without full_factor (article layout)."""
    name = entry.name.encode("latin-1", errors="replace")[:9]
    name = name.ljust(9, b"\x00")
    return (
        bytes([entry.slot & 0xFF])
        + name
        + bytes([entry.battery_type & 0xFF, entry.cells & 0xFF])
        + pack_u16(current_to_digits(entry.discharge_mA))
        + pack_u16(current_to_digits(entry.charge_mA))
        + pack_u32(capacity_to_digits(entry.capacity_mAh))
        + pack_u16(entry.pause_s)
        + pack_u16(current_to_digits(entry.forming_mA))
        + bytes([entry.flags & 0xFF])
    )


def decode_battery_db(data: bytes) -> BatteryDbEntry:
    if len(data) < 25:
        raise ValueError("Datenbank-Eintrag zu kurz")
    slot = data[0]
    name = data[1:10].split(b"\x00", 1)[0].decode("latin-1", errors="replace").strip()
    o = 10
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
    pause = u16(data, o)
    o += 2
    If = u16(data, o) if len(data) >= o + 2 else 0
    o += 2
    flags = data[o] if len(data) > o else 0
    return BatteryDbEntry(
        slot=slot,
        name=name,
        battery_type=btype,
        cells=cells,
        discharge_mA=current_from_digits(Id) or 0.0,
        charge_mA=current_from_digits(Ic) or 0.0,
        capacity_mAh=capacity_from_digits(cap),
        pause_s=pause,
        forming_mA=current_from_digits(If) or 0.0,
        flags=flags,
        full_factor=250,
    )
