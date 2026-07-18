from __future__ import annotations

from typing import Protocol

from .framing import build_frame, parse_frame
from .models import (
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
from .units import (
    capacity_from_digits,
    current_from_digits,
    temp_from_digits,
    u16,
    u32,
    voltage_from_digits,
)
from .constants import INVALID_MEASURE, SAMPLES_PER_BLOCK


class Transport(Protocol):
    def transfer(self, payload: bytes, timeout: float = 2.0) -> bytes: ...


class ProtocolClient:
    """High-level ALC 8500-2 command API."""

    def __init__(self, transport: Transport) -> None:
        self.t = transport

    def _req(self, payload: bytes, timeout: float = 2.0) -> bytes:
        frame = build_frame(payload)
        raw = self.t.transfer(frame, timeout=timeout)
        body = parse_frame(raw)
        return body

    def get_channel_params(self, channel: int) -> ChannelParams:
        body = self._req(bytes([ord("p"), channel & 0xFF]))
        if not body or body[0] not in (ord("p"), ord("P")):
            raise ValueError(f"Unerwartete Antwort auf p: {body!r}")
        return ChannelParams.decode(body[1:])

    def set_channel_params(self, params: ChannelParams) -> ChannelParams:
        body = self._req(bytes([ord("P")]) + params.encode_set(), timeout=3.0)
        if not body or body[0] not in (ord("p"), ord("P")):
            raise ValueError(f"Unerwartete Antwort auf P: {body!r}")
        return ChannelParams.decode(body[1:])

    def get_activity(self, channel: int) -> ActivityState:
        body = self._req(bytes([ord("a"), channel & 0xFF]))
        if not body or body[0] not in (ord("a"), ord("A")):
            raise ValueError(f"Unerwartete Antwort auf a: {body!r}")
        data = body[1:]
        if len(data) < 3:
            raise ValueError("Aktivitätsantwort zu kurz")
        return ActivityState(channel=data[0], action=data[1], stage=data[2])

    def set_activity(self, channel: int, stop: bool = False) -> ActivityState:
        action = 0x01 if stop else 0x00
        body = self._req(bytes([ord("A"), channel & 0xFF, action]), timeout=5.0)
        if not body or body[0] not in (ord("a"), ord("A")):
            raise ValueError(f"Unerwartete Antwort auf A: {body!r}")
        data = body[1:]
        if len(data) < 3:
            # some firmwares echo only channel+action
            stage = data[2] if len(data) > 2 else 0
            return ActivityState(channel=data[0] if data else channel, action=action, stage=stage)
        return ActivityState(channel=data[0], action=data[1], stage=data[2])

    def get_measurements(self) -> list[ChannelMeasurement]:
        body = self._req(bytes([ord("m")]))
        if not body or body[0] not in (ord("m"), ord("M")):
            raise ValueError(f"Unerwartete Antwort auf m: {body!r}")
        data = body[1:]
        # 4 channels × (U 2 + I 2 + C 4) = 32 bytes typical
        out: list[ChannelMeasurement] = []
        stride = 8
        for ch in range(4):
            o = ch * stride
            if o + stride > len(data):
                break
            u = u16(data, o)
            i = u16(data, o + 2)
            c = u32(data, o + 4)
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
        return BatteryDbEntry.decode(body[1:])

    def set_battery_db(self, entry: BatteryDbEntry) -> BatteryDbEntry:
        body = self._req(bytes([ord("D")]) + entry.encode(), timeout=3.0)
        if not body or body[0] not in (ord("d"), ord("D")):
            raise ValueError(f"Unerwartete Antwort auf D: {body!r}")
        return BatteryDbEntry.decode(body[1:])

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

    def clear_logger(self, channel: int) -> None:
        body = self._req(bytes([ord("L"), channel & 0xFF]))
        if not body or body[0] not in (ord("l"), ord("L")):
            # some firmwares ACK with short frame
            pass

    def get_logger_block(self, channel: int, block: int) -> bytes:
        body = self._req(
            bytes([ord("v"), channel & 0xFF, (block >> 8) & 0xFF, block & 0xFF]),
            timeout=5.0,
        )
        if not body or body[0] not in (ord("v"), ord("V")):
            raise ValueError(f"Unerwartete Antwort auf v: {body!r}")
        # v + ch + block(2) + 100 samples × 8 bytes
        return body[1:]

    def read_logger(self, channel: int, sample_count: int | None = None) -> LoggerData:
        params = self.get_channel_params(channel)
        count = sample_count if sample_count is not None else params.logger_samples
        blocks = max(1, (count + SAMPLES_PER_BLOCK - 1) // SAMPLES_PER_BLOCK) if count else 1
        raw_samples: list[bytes] = []
        for b in range(min(blocks, 651)):
            data = self.get_logger_block(channel, b)
            # skip ch + block header if present
            payload = data
            if len(data) >= 3 and data[0] == channel:
                payload = data[3:]
            # 100 × 8 bytes
            for i in range(SAMPLES_PER_BLOCK):
                o = i * 8
                if o + 8 > len(payload):
                    break
                raw_samples.append(payload[o : o + 8])

        header = LoggerHeader()
        samples: list[LoggerSample] = []
        # First 3 records are header fields per manual
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
                capacity_mAh=capacity_from_digits(u32(h2, 2) & 0xFFFFFFFF) if len(h2) >= 6 else 0,
                charge_mA=current_from_digits(u16(h2, 6)) or 0 if len(h2) >= 8 else 0,
                discharge_mA=current_from_digits(u16(h3, 2)) or 0 if len(h3) >= 4 else 0,
                forming_mA=current_from_digits(u16(h3, 4)) or 0 if len(h3) >= 6 else 0,
                pause_s=u16(h3, 6) if len(h3) >= 8 else 0,
            )
            # Fix capacity/charge packing from field2: type, cells, capacity(4), charge(2) = 8
            if len(h2) >= 8:
                header.capacity_mAh = capacity_from_digits(u32(h2, 2))
                header.charge_mA = current_from_digits(u16(h2, 6)) or 0
            if len(h3) >= 8:
                header.battery_type = h3[0] if h3[0] else header.battery_type
                header.cells = h3[1] if h3[1] else header.cells
                header.discharge_mA = current_from_digits(u16(h3, 2)) or 0
                header.forming_mA = current_from_digits(u16(h3, 4)) or 0
                header.pause_s = u16(h3, 6)
            measure_records = raw_samples[3:]
        else:
            measure_records = raw_samples

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
