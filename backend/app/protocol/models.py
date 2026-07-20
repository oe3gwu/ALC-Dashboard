from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .constants import (
    BATTERY_TYPES,
    FLAG_ACTIVATOR,
    PROGRAMS,
    stage_from_byte,
)
from .units import (
    capacity_from_digits,
    capacity_to_digits,
    current_from_digits,
    current_to_digits,
    pack_u16,
    pack_u32,
    u16,
    u32,
    voltage_from_digits,
)


@dataclass
class ChannelParams:
    channel: int = 0
    battery_slot: int = 0x28
    battery_type: int = 0x01
    cells: int = 1
    discharge_mA: float = 500.0
    charge_mA: float = 500.0
    capacity_mAh: float = 2000.0
    program: int = 0x01
    forming_mA: float = 0.0
    pause_s: int = 60
    flags: int = 0
    full_factor: int = 250  # 250 = off
    logger_samples: int = 0
    stage: int = 0

    @property
    def battery_type_name(self) -> str:
        return BATTERY_TYPES.get(self.battery_type, f"0x{self.battery_type:02X}")

    @property
    def program_name(self) -> str:
        return PROGRAMS.get(self.program, f"0x{self.program:02X}")

    @property
    def stage_name(self) -> str:
        return stage_from_byte(self.stage)

    @property
    def activator(self) -> bool:
        return bool(self.flags & FLAG_ACTIVATOR)

    @activator.setter
    def activator(self, value: bool) -> None:
        if value:
            self.flags |= FLAG_ACTIVATOR
        else:
            self.flags &= ~FLAG_ACTIVATOR

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["battery_type_name"] = self.battery_type_name
        d["program_name"] = self.program_name
        d["stage_name"] = self.stage_name
        d["activator"] = self.activator
        d["idle"] = self.stage_name == "Leerlauf"
        return d

    def encode_set(self) -> bytes:
        """Encode P payload (without command byte)."""
        return (
            bytes(
                [
                    self.channel & 0xFF,
                    self.battery_slot & 0xFF,
                    self.battery_type & 0xFF,
                    self.cells & 0xFF,
                ]
            )
            + pack_u16(current_to_digits(self.discharge_mA))
            + pack_u16(current_to_digits(self.charge_mA))
            + pack_u32(capacity_to_digits(self.capacity_mAh))
            + bytes([self.program & 0xFF])
            + pack_u16(current_to_digits(self.forming_mA))
            + pack_u16(self.pause_s & 0xFFFF)
            + bytes([self.flags & 0xFF, self._wire_full_factor()])
        )

    def _wire_full_factor(self) -> int:
        """API 250 = off; FW 2.08 stores off as 0 on the wire."""
        ff = int(self.full_factor)
        if ff <= 0 or ff >= 250:
            return 0
        return ff & 0xFF

    @classmethod
    def decode(cls, data: bytes) -> ChannelParams:
        """Decode p/P response body after command letter."""
        # Expected layout after 'p'/'P':
        # ch(1) slot(1) type(1) cells(1) Id(2) Ic(2) Cap(4) prog(1) If(2) pause(2) flags(1) full(1)
        # + logger samples(2) + stage(1) on read responses
        # 19 bytes core params; optional +2 logger samples +1 stage on reads
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
        full = data[o]
        o += 1
        # FW 2.08: off is 0; API / ChargeProfessional use 250 = off
        if full == 0:
            full = 250
        logger = 0
        stage = 0
        if len(data) >= o + 2:
            logger = u16(data, o)
            o += 2
        if len(data) > o:
            stage = data[o]
        return cls(
            channel=ch,
            battery_slot=slot,
            battery_type=btype,
            cells=cells,
            discharge_mA=current_from_digits(Id) or 0.0,
            charge_mA=current_from_digits(Ic) or 0.0,
            capacity_mAh=capacity_from_digits(cap),
            program=prog,
            forming_mA=(current_from_digits(If) or 0.0),
            pause_s=pause,
            flags=flags,
            full_factor=full,
            logger_samples=logger,
            stage=stage,
        )


@dataclass
class ChannelMeasurement:
    channel: int
    voltage_V: float | None
    current_mA: float | None
    capacity_mAh: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Temperatures:
    battery_C: float | None = None
    psu_C: float | None = None
    heatsink_C: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActivityState:
    channel: int
    action: int  # 0 start, 1 stop
    stage: int

    @property
    def stage_name(self) -> str:
        return stage_from_byte(self.stage)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "action": self.action,
            "stage": self.stage,
            "stage_name": self.stage_name,
        }


@dataclass
class BatteryDbEntry:
    slot: int
    name: str = ""
    battery_type: int = 0x01
    cells: int = 1
    discharge_mA: float = 500.0
    charge_mA: float = 500.0
    capacity_mAh: float = 2000.0
    pause_s: int = 60
    forming_mA: float = 0.0
    flags: int = 0
    full_factor: int = 250

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["battery_type_name"] = BATTERY_TYPES.get(self.battery_type, "?")
        return d

    def encode(self) -> bytes:
        """Classic 8500-2 / simulator layout: Id, Ic, Cap + full_factor."""
        name = self.name.encode("latin-1", errors="replace")[:9]
        name = name.ljust(9, b"\x00")
        return (
            bytes([self.slot & 0xFF])
            + name
            + bytes([self.battery_type & 0xFF, self.cells & 0xFF])
            + pack_u16(current_to_digits(self.discharge_mA))
            + pack_u16(current_to_digits(self.charge_mA))
            + pack_u32(capacity_to_digits(self.capacity_mAh))
            + pack_u16(self.pause_s)
            + pack_u16(current_to_digits(self.forming_mA))
            + bytes([self.flags & 0xFF, self.full_factor & 0xFF])
        )

    def encode_fw208(self) -> bytes:
        """FW 2.08 (Ident h) DB layout: Cap, Id, Ic, pause, flags, full_factor, function (25 B).

        Real device ``d`` replies (e.g. AUTO slot) end with ``flags | full | 0xFF`` — there is
        no forming-current field in this layout (unlike classic 26-byte Id/Ic/Cap frames).
        """
        name = self.name.encode("latin-1", errors="replace")[:9]
        name = name.ljust(9, b" ")
        ff = int(self.full_factor)
        if ff <= 0 or ff >= 250:
            ff = 0
        else:
            ff = ff & 0xFF
        return (
            bytes([self.slot & 0xFF])
            + name
            + bytes([self.battery_type & 0xFF, self.cells & 0xFF])
            + pack_u32(capacity_to_digits(self.capacity_mAh))
            + pack_u16(current_to_digits(self.discharge_mA))
            + pack_u16(current_to_digits(self.charge_mA))
            + pack_u16(self.pause_s)
            + bytes([self.flags & 0xFF, ff, 0xFF])
        )

    @classmethod
    def decode(cls, data: bytes) -> BatteryDbEntry:
        # Classic / simulator: 26 bytes — Id, Ic, Cap, pause, forming, flags, full.
        # FW 2.08 (Ident h): 25 bytes — Cap, Id, Ic, pause, flags, full, function (no forming).
        if len(data) < 24:
            raise ValueError("Datenbank-Eintrag zu kurz")
        slot = data[0]
        name = data[1:10].split(b"\x00", 1)[0].decode("latin-1", errors="replace").strip()
        o = 10
        btype = data[o]
        o += 1
        cells = data[o]
        o += 1
        # Documented order: Id, Ic, Cap. FW 2.08 occupied slots store Cap, Id, Ic instead.
        Id = u16(data, o)
        Ic = u16(data, o + 2)
        Cap = u32(data, o + 4)
        if capacity_from_digits(Cap) > 50_000:
            Cap = u32(data, o)
            Id = u16(data, o + 4)
            Ic = u16(data, o + 6)
        o += 8
        pause = u16(data, o)
        o += 2
        rest = len(data) - o
        forming = 0.0
        flags = 0
        full = 250
        if rest >= 4:
            # Classic trailer: forming(2) + flags + full
            forming = current_from_digits(u16(data, o)) or 0.0
            o += 2
            flags = data[o]
            o += 1
            full = data[o] if len(data) > o else 250
        elif rest >= 2:
            # FW 2.08 trailer: flags + full [+ function 0xFF]
            flags = data[o]
            o += 1
            full = data[o]
            o += 1
        elif rest == 1:
            flags = data[o]
        # Wire 0 = off (same idea as channel P on this FW)
        if full == 0:
            full = 250
        if btype == 0xFF:
            return cls(
                slot=slot,
                name="",
                battery_type=0xFF,
                cells=0,
                discharge_mA=0.0,
                charge_mA=0.0,
                capacity_mAh=0.0,
                pause_s=0,
                forming_mA=0.0,
                flags=0,
                full_factor=250,
            )
        return cls(
            slot=slot,
            name=name,
            battery_type=btype,
            cells=cells,
            discharge_mA=current_from_digits(Id) or 0.0,
            charge_mA=current_from_digits(Ic) or 0.0,
            capacity_mAh=capacity_from_digits(Cap),
            pause_s=pause,
            forming_mA=forming,
            flags=flags,
            full_factor=full,
        )


@dataclass
class DeviceParamsG:
    """g/G — discharge cutoffs, cycle counts, -dU, pause minutes."""

    discharge_NiCd_mV: int = 900
    discharge_NiMH_mV: int = 900
    discharge_LiIon_mV: int = 3000
    discharge_LiPo_mV: int = 3100
    discharge_Pb_mV: int = 1850
    pause_min: int = 1
    cycles_cycle_NiCd: int = 5
    cycles_cycle_NiMH: int = 5
    cycles_form_NiCd: int = 5
    cycles_form_NiMH: int = 5
    dU_NiCd: int = 40  # /100 = %
    dU_NiMH: int = 20

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["discharge_NiCd_V"] = self.discharge_NiCd_mV / 1000
        d["discharge_NiMH_V"] = self.discharge_NiMH_mV / 1000
        d["discharge_LiIon_V"] = self.discharge_LiIon_mV / 1000
        d["discharge_LiPo_V"] = self.discharge_LiPo_mV / 1000
        d["discharge_Pb_V"] = self.discharge_Pb_mV / 1000
        d["dU_NiCd_pct"] = self.dU_NiCd / 100
        d["dU_NiMH_pct"] = self.dU_NiMH / 100
        return d

    def encode(self) -> bytes:
        return (
            pack_u16(self.discharge_NiCd_mV)
            + pack_u16(self.discharge_NiMH_mV)
            + pack_u16(self.discharge_LiIon_mV)
            + pack_u16(self.discharge_LiPo_mV)
            + pack_u16(self.discharge_Pb_mV)
            + bytes(
                [
                    self.pause_min & 0xFF,
                    self.cycles_cycle_NiCd & 0xFF,
                    self.cycles_cycle_NiMH & 0xFF,
                    self.cycles_form_NiCd & 0xFF,
                    self.cycles_form_NiMH & 0xFF,
                    self.dU_NiCd & 0xFF,
                    self.dU_NiMH & 0xFF,
                ]
            )
        )

    @classmethod
    def decode(cls, data: bytes) -> DeviceParamsG:
        if len(data) < 17:
            raise ValueError("Geräteparameter g zu kurz")
        return cls(
            discharge_NiCd_mV=u16(data, 0),
            discharge_NiMH_mV=u16(data, 2),
            discharge_LiIon_mV=u16(data, 4),
            discharge_LiPo_mV=u16(data, 6),
            discharge_Pb_mV=u16(data, 8),
            pause_min=data[10],
            cycles_cycle_NiCd=data[11],
            cycles_cycle_NiMH=data[12],
            cycles_form_NiCd=data[13],
            cycles_form_NiMH=data[14],
            dU_NiCd=data[15],
            dU_NiMH=data[16],
        )


@dataclass
class DeviceParamsH:
    """h/H — charge / maintain voltages for Li/Pb."""

    reserved: list[int] = field(default_factory=lambda: [0x05DC] * 4)
    charge_LiIon_mV: int = 4100
    maintain_LiIon_mV: int = 4050
    charge_LiPo_mV: int = 4200
    maintain_LiPo_mV: int = 4150
    charge_Pb_mV: int = 2350
    maintain_Pb_mV: int = 2260
    unused: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "charge_LiIon_V": self.charge_LiIon_mV / 1000,
            "maintain_LiIon_V": self.maintain_LiIon_mV / 1000,
            "charge_LiPo_V": self.charge_LiPo_mV / 1000,
            "maintain_LiPo_V": self.maintain_LiPo_mV / 1000,
            "charge_Pb_V": self.charge_Pb_mV / 1000,
            "maintain_Pb_V": self.maintain_Pb_mV / 1000,
            "charge_LiIon_mV": self.charge_LiIon_mV,
            "maintain_LiIon_mV": self.maintain_LiIon_mV,
            "charge_LiPo_mV": self.charge_LiPo_mV,
            "maintain_LiPo_mV": self.maintain_LiPo_mV,
            "charge_Pb_mV": self.charge_Pb_mV,
            "maintain_Pb_mV": self.maintain_Pb_mV,
        }

    def encode(self) -> bytes:
        body = b"".join(pack_u16(v) for v in self.reserved)
        body += (
            pack_u16(self.charge_LiIon_mV)
            + pack_u16(self.maintain_LiIon_mV)
            + pack_u16(self.charge_LiPo_mV)
            + pack_u16(self.maintain_LiPo_mV)
            + pack_u16(self.charge_Pb_mV)
            + pack_u16(self.maintain_Pb_mV)
            + pack_u16(self.unused)
        )
        return body

    @classmethod
    def decode(cls, data: bytes) -> DeviceParamsH:
        # 8 reserved + 12 voltage fields + 2 unused = 22
        if len(data) < 20:
            raise ValueError("Geräteparameter h zu kurz")
        return cls(
            reserved=[u16(data, i) for i in range(0, 8, 2)],
            charge_LiIon_mV=u16(data, 8),
            maintain_LiIon_mV=u16(data, 10),
            charge_LiPo_mV=u16(data, 12),
            maintain_LiPo_mV=u16(data, 14),
            charge_Pb_mV=u16(data, 16),
            maintain_Pb_mV=u16(data, 18),
            unused=u16(data, 20) if len(data) >= 22 else 0,
        )


@dataclass
class DeviceParamsJ:
    """j/J — LiFePO4, illumination, beeps, contrast."""

    discharge_LiFePO4_mV: int = 2300
    placeholder: int = 0
    charge_LiFePO4_mV: int = 3650
    maintain_LiFePO4_mV: int = 3450
    placeholder2: int = 0
    setup_flags: int = 0x01  # illumination + beeps
    contrast: int = 8

    @property
    def illumination(self) -> int:
        return self.setup_flags & 0x07

    @property
    def alarm_beep(self) -> bool:
        return bool(self.setup_flags & 0x08)

    @property
    def button_beep(self) -> bool:
        return bool(self.setup_flags & 0x10)

    def to_dict(self) -> dict[str, Any]:
        return {
            "discharge_LiFePO4_V": self.discharge_LiFePO4_mV / 1000,
            "charge_LiFePO4_V": self.charge_LiFePO4_mV / 1000,
            "maintain_LiFePO4_V": self.maintain_LiFePO4_mV / 1000,
            "discharge_LiFePO4_mV": self.discharge_LiFePO4_mV,
            "charge_LiFePO4_mV": self.charge_LiFePO4_mV,
            "maintain_LiFePO4_mV": self.maintain_LiFePO4_mV,
            "illumination": self.illumination,
            "alarm_beep": self.alarm_beep,
            "button_beep": self.button_beep,
            "setup_flags": self.setup_flags,
            "contrast": self.contrast,
        }

    def encode(self) -> bytes:
        return (
            pack_u16(self.discharge_LiFePO4_mV)
            + bytes([self.placeholder & 0xFF])
            + pack_u16(self.charge_LiFePO4_mV)
            + pack_u16(self.maintain_LiFePO4_mV)
            + bytes([self.placeholder2 & 0xFF, self.setup_flags & 0xFF, self.contrast & 0xFF])
        )

    @classmethod
    def decode(cls, data: bytes) -> DeviceParamsJ:
        if len(data) < 9:
            raise ValueError("Geräteparameter j zu kurz")
        return cls(
            discharge_LiFePO4_mV=u16(data, 0),
            placeholder=data[2],
            charge_LiFePO4_mV=u16(data, 3),
            maintain_LiFePO4_mV=u16(data, 5),
            placeholder2=data[7] if len(data) > 7 else 0,
            setup_flags=data[8] if len(data) > 8 else 1,
            contrast=data[9] if len(data) > 9 else 8,
        )


@dataclass
class LoggerSample:
    voltage_V: float | None
    current_mA: float | None
    capacity_mAh: float | None
    marker: str | None = None  # P=pause, M=missing

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LoggerHeader:
    battery_slot: int = 0
    program: int = 0
    time_sec: int = 0
    time_min: int = 0
    time_hour: int = 0
    time_day: int = 1
    time_month: int = 1
    time_year: int = 0
    battery_type: int = 0
    cells: int = 0
    capacity_mAh: float = 0
    charge_mA: float = 0
    discharge_mA: float = 0
    forming_mA: float = 0
    pause_s: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["program_name"] = PROGRAMS.get(self.program, "?")
        d["battery_type_name"] = BATTERY_TYPES.get(self.battery_type, "?")
        return d


@dataclass
class LoggerData:
    channel: int
    header: LoggerHeader
    samples: list[LoggerSample] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "header": self.header.to_dict(),
            "samples": [s.to_dict() for s in self.samples],
            "sample_count": len(self.samples),
        }


def parse_ident_u(data: bytes) -> tuple[str, str]:
    """Parse ``u`` body after command letter: FW(10) + pad(2) + SN(10).

    Classic padding uses ``00h``; FW 2.08 (Ident ``h``) often uses ``FFh``.
    Returns ``(firmware, serial)`` with firmware like ``h   V2.08``.
    """
    if len(data) < 10:
        raise ValueError("u-Antwort zu kurz")

    def _clean_field(raw: bytes) -> str:
        # Truncate at NUL, then strip trailing 0xFF pad bytes
        cut = raw.split(b"\x00", 1)[0]
        while cut.endswith(b"\xff"):
            cut = cut[:-1]
        return cut.decode("ascii", errors="replace").strip()

    fw = _clean_field(data[0:10])
    sn = ""
    if len(data) >= 22:
        sn = _clean_field(data[12:22])
    elif len(data) > 12:
        sn = _clean_field(data[12:])
    return fw, sn
