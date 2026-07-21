"""High-level client for ALC 5000 Mobile (Ident j, FW > 2.00 only)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from app.protocol.alc5000 import models as wire
from app.protocol.alc5000.constants import (
    A_STOP,
    CHANNEL_COUNT,
    IDENT_5000_FW2,
    IDENT_5000_LEGACY,
    INVALID_MEASURE,
    PROG_TO_A_START,
    SAMPLES_PER_BLOCK,
)
from app.protocol.alc5000.framing import build_frame, parse_frame
from app.protocol.models import (
    ActivityState,
    BatteryDbEntry,
    ChannelMeasurement,
    ChannelParams,
    DeviceParamsG,
    DeviceParamsH,
    DeviceParamsJ,
    LoggerData,
    LoggerHeader,
    LoggerSample,
    Temperatures,
)
from app.protocol.units import (
    capacity_from_digits,
    current_from_digits,
    temp_from_digits,
    u16,
    u32,
    voltage_from_digits,
)


class UnsupportedAlc5000Error(RuntimeError):
    """Raised when Ident is not `j` (supported 5000 Mobile FW > 2.00)."""


class Transport(Protocol):
    def transfer(self, payload: bytes, timeout: float = 2.0) -> bytes: ...


class Alc5000Client:
    """API-compatible with ProtocolClient; 2 channels; Vollfaktor + RTC."""

    def __init__(self, transport: Transport, channel_count: int = CHANNEL_COUNT) -> None:
        self.t = transport
        self.channel_count = channel_count
        self.firmware = ""
        self.serial_number = ""
        self._identified = False

    def _req(self, payload: bytes, timeout: float = 2.0) -> bytes:
        frame = build_frame(payload)
        raw = self.t.transfer(frame, timeout=timeout)
        return parse_frame(raw)

    def read_ident_u(self) -> tuple[str, str]:
        body = self._req(bytes([ord("u")]))
        if not body or body[0] not in (ord("u"), ord("U")):
            raise ValueError(f"Unerwartete Antwort auf u: {body!r}")
        fw, sn = wire.parse_u_payload(body[1:])
        self.firmware = fw
        self.serial_number = sn
        return fw, sn

    def ensure_supported_device(self) -> str:
        """Connect gate: first char of FW field must be `j` (PDF p.4)."""
        fw, _sn = self.read_ident_u()
        prefix = fw[:1] if fw else ""
        if prefix == IDENT_5000_LEGACY:
            raise UnsupportedAlc5000Error(
                "Nicht unterstützte Firmware (Ident f — ALC 5000 Mobile FW < 2.00)"
            )
        if prefix != IDENT_5000_FW2:
            raise UnsupportedAlc5000Error(
                f"Nicht unterstütztes Gerät (Ident '{prefix or '?'}', erwartet '{IDENT_5000_FW2}')"
            )
        self._identified = True
        return fw

    def get_channel_params(self, channel: int = 0) -> ChannelParams:
        ch = channel & 0xFF
        body = self._req(bytes([ord("p"), ch]))
        if not body or body[0] not in (ord("p"), ord("P")):
            raise ValueError(f"Unerwartete Antwort auf p: {body!r}")
        return wire.decode_channel_params(body[1:])

    def set_channel_params(self, params: ChannelParams) -> ChannelParams:
        body = self._req(bytes([ord("P")]) + wire.encode_channel_set(params), timeout=3.0)
        if not body or body[0] not in (ord("p"), ord("P")):
            raise ValueError(f"Unerwartete Antwort auf P: {body!r}")
        return wire.decode_channel_params(body[1:])

    def get_activity(self, channel: int = 0) -> ActivityState:
        ch = channel & 0xFF
        body = self._req(bytes([ord("a"), ch]))
        if not body or body[0] not in (ord("a"), ord("A")):
            raise ValueError(f"Unerwartete Antwort auf a: {body!r}")
        data = body[1:]
        if len(data) < 2:
            raise ValueError("Aktivitätsantwort zu kurz")
        # PDF: a + Kanal + Ladestufe (no action byte)
        return ActivityState(channel=data[0], action=0, stage=data[1])

    def set_activity(self, channel: int = 0, stop: bool = False) -> ActivityState:
        ch = channel & 0xFF
        if stop:
            action = A_STOP
        else:
            prog = self.get_channel_params(ch).program
            action = PROG_TO_A_START.get(prog, 0x00)
        body = self._req(bytes([ord("A"), ch, action]), timeout=5.0)
        if not body or body[0] not in (ord("a"), ord("A")):
            raise ValueError(f"Unerwartete Antwort auf A: {body!r}")
        data = body[1:]
        stage = data[1] if len(data) >= 2 else 0
        return ActivityState(channel=data[0] if data else ch, action=action, stage=stage)

    def get_measurements(self) -> list[ChannelMeasurement]:
        out: list[ChannelMeasurement] = []
        for ch in range(self.channel_count):
            body = self._req(bytes([ord("m"), ch & 0xFF]))
            if not body or body[0] not in (ord("m"), ord("M")):
                raise ValueError(f"Unerwartete Antwort auf m: {body!r}")
            data = body[1:]
            # m + channel + U I Cap
            if len(data) >= 1 and data[0] == ch:
                data = data[1:]
            if len(data) < 8:
                out.append(ChannelMeasurement(channel=ch, voltage_V=None, current_mA=None, capacity_mAh=None))
                continue
            u = u16(data, 0)
            i = u16(data, 2)
            c = u32(data, 4)
            out.append(
                ChannelMeasurement(
                    channel=ch,
                    voltage_V=voltage_from_digits(u),
                    current_mA=current_from_digits(i, allow_invalid=True),
                    capacity_mAh=capacity_from_digits(c) if c != 0xFFFFFFFF else None,
                )
            )
        return out

    def get_temperatures(self) -> Temperatures:
        body = self._req(bytes([ord("t")]))
        if not body or body[0] not in (ord("t"), ord("T")):
            raise ValueError(f"Unerwartete Antwort auf t: {body!r}")
        data = body[1:]
        bat = temp_from_digits(u16(data, 0)) if len(data) >= 2 else None
        psu = temp_from_digits(u16(data, 2)) if len(data) >= 4 else None
        sink = temp_from_digits(u16(data, 4)) if len(data) >= 6 else None
        return Temperatures(battery_C=bat, psu_C=psu, heatsink_C=sink)

    def get_battery_db(self, slot: int) -> BatteryDbEntry:
        body = self._req(bytes([ord("d"), slot & 0xFF]))
        if not body or body[0] not in (ord("d"), ord("D")):
            raise ValueError(f"Unerwartete Antwort auf d: {body!r}")
        return wire.decode_battery_db(body[1:])

    def set_battery_db(self, entry: BatteryDbEntry) -> BatteryDbEntry:
        body = self._req(bytes([ord("D")]) + wire.encode_battery_db(entry), timeout=3.0)
        if not body or body[0] not in (ord("d"), ord("D")):
            raise ValueError(f"Unerwartete Antwort auf D: {body!r}")
        return wire.decode_battery_db(body[1:])

    def get_device_g(self) -> DeviceParamsG:
        body = self._req(bytes([ord("g")]))
        if not body or body[0] not in (ord("g"), ord("G")):
            raise ValueError(f"Unerwartete Antwort auf g: {body!r}")
        return DeviceParamsG.decode(body[1:])

    def set_device_g(self, params: DeviceParamsG) -> DeviceParamsG:
        body = self._req(bytes([ord("G")]) + params.encode(), timeout=3.0)
        if not body or body[0] not in (ord("g"), ord("G")):
            raise ValueError(f"Unerwartete Antwort auf G: {body!r}")
        return DeviceParamsG.decode(body[1:])

    def get_device_h(self) -> DeviceParamsH:
        body = self._req(bytes([ord("h")]))
        if not body or body[0] not in (ord("h"), ord("H")):
            raise ValueError(f"Unerwartete Antwort auf h: {body!r}")
        return DeviceParamsH.decode(body[1:])

    def set_device_h(self, params: DeviceParamsH) -> DeviceParamsH:
        body = self._req(bytes([ord("H")]) + params.encode(), timeout=3.0)
        if not body or body[0] not in (ord("h"), ord("H")):
            raise ValueError(f"Unerwartete Antwort auf H: {body!r}")
        return DeviceParamsH.decode(body[1:])

    def get_device_j(self) -> DeviceParamsJ:
        body = self._req(bytes([ord("j")]))
        if not body or body[0] not in (ord("j"), ord("J")):
            raise ValueError(f"Unerwartete Antwort auf j: {body!r}")
        return DeviceParamsJ.decode(body[1:])

    def set_device_j(self, params: DeviceParamsJ) -> DeviceParamsJ:
        body = self._req(bytes([ord("J")]) + params.encode(), timeout=3.0)
        if not body or body[0] not in (ord("j"), ord("J")):
            raise ValueError(f"Unerwartete Antwort auf J: {body!r}")
        return DeviceParamsJ.decode(body[1:])

    def get_rtc(self) -> tuple[int, int, int, int, int, int]:
        """c — real-time clock (5000 Mobile only). Returns sec,min,hour,day,month,year."""
        body = self._req(bytes([ord("c")]))
        if not body or body[0] not in (ord("c"), ord("C")):
            raise ValueError(f"Unerwartete Antwort auf c: {body!r}")
        return wire.decode_rtc(body[1:])

    def set_rtc(self, sec: int, minute: int, hour: int, day: int, month: int, year: int) -> tuple[int, ...]:
        body = self._req(bytes([ord("C")]) + wire.encode_rtc(sec, minute, hour, day, month, year), timeout=3.0)
        if not body or body[0] not in (ord("c"), ord("C")):
            raise ValueError(f"Unerwartete Antwort auf C: {body!r}")
        return wire.decode_rtc(body[1:])

    def clear_logger(self, channel: int = 0) -> None:
        body = self._req(bytes([ord("L"), channel & 0xFF]))
        if not body or body[0] not in (ord("l"), ord("L")):
            pass

    def get_logger_block(self, channel: int, block: int) -> bytes:
        body = self._req(
            bytes([ord("v"), channel & 0xFF, (block >> 8) & 0xFF, block & 0xFF]),
            timeout=5.0,
        )
        if not body or body[0] not in (ord("v"), ord("V")):
            raise ValueError(f"Unerwartete Antwort auf v: {body!r}")
        return body[1:]

    def read_logger(
        self,
        channel: int = 0,
        sample_count: int | None = None,
        on_progress: Callable[[int, int, int], None] | None = None,
    ) -> LoggerData:
        params = self.get_channel_params(channel)
        count = sample_count if sample_count is not None else params.logger_samples
        blocks = max(1, (count + SAMPLES_PER_BLOCK - 1) // SAMPLES_PER_BLOCK) if count else 1
        total_blocks = min(blocks, 651)
        if on_progress:
            on_progress(0, total_blocks, int(count or 0))
        raw_samples: list[bytes] = []
        for b in range(total_blocks):
            data = self.get_logger_block(channel, b)
            payload = data
            if len(data) >= 3 and data[0] == (channel & 0xFF):
                payload = data[3:]
            for i in range(SAMPLES_PER_BLOCK):
                o = i * 8
                if o + 8 > len(payload):
                    break
                raw_samples.append(payload[o : o + 8])
            if on_progress:
                on_progress(b + 1, total_blocks, int(count or 0))

        header = LoggerHeader()
        if len(raw_samples) >= 3:
            h1, h2, h3 = raw_samples[0], raw_samples[1], raw_samples[2]
            header = LoggerHeader(
                battery_slot=h1[0],
                program=h1[1],
                time_sec=h1[2],
                time_min=h1[3],
                time_hour=h1[4],
                time_day=h1[5],
                time_month=h1[6],
                time_year=h1[7],
                battery_type=h2[0],
                cells=h2[1],
                capacity_mAh=capacity_from_digits(u32(h2, 2)) if len(h2) >= 6 else 0,
                charge_mA=current_from_digits(u16(h2, 6)) or 0 if len(h2) >= 8 else 0,
                discharge_mA=current_from_digits(u16(h3, 2)) or 0 if len(h3) >= 4 else 0,
                forming_mA=current_from_digits(u16(h3, 4)) or 0 if len(h3) >= 6 else 0,
                pause_s=u16(h3, 6) if len(h3) >= 8 else 0,
            )
            measure_records = raw_samples[3:]
        else:
            measure_records = raw_samples

        samples: list[LoggerSample] = []
        for rec in measure_records[:count] if count else measure_records:
            u = u16(rec, 0)
            i = u16(rec, 2)
            c = u32(rec, 4) if len(rec) >= 8 else 0
            marker = None
            if u == INVALID_MEASURE:
                marker = "M"
            elif i == INVALID_MEASURE:
                marker = "P"
            samples.append(
                LoggerSample(
                    voltage_V=voltage_from_digits(u),
                    current_mA=current_from_digits(i, allow_invalid=True),
                    capacity_mAh=capacity_from_digits(c) if c != 0xFFFFFFFF else None,
                    marker=marker,
                )
            )
        return LoggerData(channel=channel, header=header, samples=samples)
