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
    parse_ident_u,
)
from .units import (
    capacity_from_digits,
    current_from_digits,
    temp_from_digits,
    u16,
    u32,
    voltage_from_digits,
)
from .constants import INVALID_MEASURE, MAX_LOGGER_BLOCKS, SAMPLES_PER_BLOCK


class Transport(Protocol):
    def transfer(self, payload: bytes, timeout: float = 2.0) -> bytes: ...


class ProtocolClient:
    """High-level ALC 8500-2 command API."""

    def __init__(self, transport: Transport) -> None:
        self.t = transport
        self.firmware: str = ""
        self.serial_number: str = ""

    def _req(self, payload: bytes, timeout: float = 2.0) -> bytes:
        frame = build_frame(payload)
        raw = self.t.transfer(frame, timeout=timeout)
        body = parse_frame(raw)
        return body

    def read_ident_u(self) -> tuple[str, str]:
        """Ident ``u``: firmware field (prefix + version) and serial number."""
        body = self._req(bytes([ord("u")]))
        if not body or body[0] not in (ord("u"), ord("U")):
            raise ValueError(f"Unerwartete Antwort auf u: {body!r}")
        fw, sn = parse_ident_u(body[1:])
        self.firmware = fw
        self.serial_number = sn
        return fw, sn

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
        if len(data) < 2:
            raise ValueError("Aktivitätsantwort zu kurz")
        # Classic manual: ch + action + stage. FW 2.08 (Ident h): ch + stage only.
        if len(data) >= 3:
            return ActivityState(channel=data[0], action=data[1], stage=data[2])
        return ActivityState(channel=data[0], action=0, stage=data[1])

    def set_activity(self, channel: int, stop: bool = False) -> ActivityState:
        action = 0x01 if stop else 0x00
        body = self._req(bytes([ord("A"), channel & 0xFF, action]), timeout=5.0)
        if not body or body[0] not in (ord("a"), ord("A")):
            raise ValueError(f"Unerwartete Antwort auf A: {body!r}")
        data = body[1:]
        if len(data) >= 3:
            return ActivityState(channel=data[0], action=data[1], stage=data[2])
        if len(data) >= 2:
            return ActivityState(channel=data[0], action=action, stage=data[1])
        return ActivityState(channel=data[0] if data else channel, action=action, stage=0)

    def _parse_measurement(self, channel: int, data: bytes) -> ChannelMeasurement:
        if len(data) < 8:
            return ChannelMeasurement(channel=channel, voltage_V=0.0, current_mA=0.0, capacity_mAh=0.0)
        u = u16(data, 0)
        i = u16(data, 2)
        c = u32(data, 4)
        return ChannelMeasurement(
            channel=channel,
            voltage_V=voltage_from_digits(u),
            current_mA=current_from_digits(i, allow_invalid=True),
            capacity_mAh=capacity_from_digits(c) if c != 0xFFFFFFFF else None,
        )

    def get_measurements(self) -> list[ChannelMeasurement]:
        """Read live U/I/C.

        Manual / simulator: one ``m`` → 4×(U,I,C) = 32 data bytes.
        FW 2.08 (Ident ``h``, e.g. WEQ…): ``m`` + channel → ch + U/I/C (bare ``m`` often NAK).
        """
        body = self._req(bytes([ord("m"), 0x00]))
        if not body or body[0] not in (ord("m"), ord("M")):
            body = self._req(bytes([ord("m")]))
        if not body or body[0] not in (ord("m"), ord("M")):
            raise ValueError(f"Unerwartete Antwort auf m: {body!r}")
        data = body[1:]

        # All-channel blob (simulator / older firmware)
        if len(data) >= 32:
            return [self._parse_measurement(ch, data[ch * 8 : ch * 8 + 8]) for ch in range(4)]

        # Per-channel (FW 2.08): optional echoed channel byte + 8 payload bytes
        out: list[ChannelMeasurement] = []
        for ch in range(4):
            if ch == 0:
                chunk = data
            else:
                body = self._req(bytes([ord("m"), ch & 0xFF]))
                if not body or body[0] not in (ord("m"), ord("M")):
                    raise ValueError(f"Unerwartete Antwort auf m/{ch}: {body!r}")
                chunk = body[1:]
            if chunk and chunk[0] == ch and len(chunk) >= 9:
                chunk = chunk[1:]
            out.append(self._parse_measurement(ch, chunk))
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
        payload = bytes([ord("d"), slot & 0xFF])
        last: bytes | None = None
        for attempt in range(3):
            body = self._req(payload)
            if body and body[0] in (ord("d"), ord("D")):
                return BatteryDbEntry.decode(body[1:])
            last = body
            if body == bytes([0x04]) and attempt < 2:
                try:
                    self.get_channel_params(0)
                except Exception:
                    pass
                continue
            break
        raise ValueError(f"Unerwartete Antwort auf d: {last!r}")

    def set_battery_db(self, entry: BatteryDbEntry) -> BatteryDbEntry:
        # Prefer FW 2.08 layout (matches device ``d`` replies); fall back to classic.
        payloads = (
            bytes([ord("D")]) + entry.encode_fw208(),
            bytes([ord("D")]) + entry.encode()[:-1],  # Id/Ic/Cap, no full_factor
            bytes([ord("D")]) + entry.encode(),
        )
        last: bytes | None = None
        for payload in payloads:
            for attempt in range(2):
                body = self._req(payload, timeout=3.0)
                if body and body[0] in (ord("d"), ord("D")):
                    return BatteryDbEntry.decode(body[1:])
                last = body
                if body == bytes([0x04]) and attempt == 0:
                    try:
                        self.get_channel_params(0)
                    except Exception:
                        pass
                    continue
                break
        raise ValueError(f"Unerwartete Antwort auf D: {last!r}")

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
        payload = bytes([ord("v"), channel & 0xFF, (block >> 8) & 0xFF, block & 0xFF])
        last: bytes | None = None
        for attempt in range(3):
            body = self._req(payload, timeout=5.0)
            if body and body[0] in (ord("v"), ord("V")):
                return body[1:]
            last = body
            # NAK 04h — same recovery as bare ``m`` after unused-channel polls
            if body == bytes([0x04]) and attempt < 2:
                try:
                    self.get_channel_params(channel)
                except Exception:
                    pass
                continue
            break
        raise ValueError(f"Unerwartete Antwort auf v: {last!r}")

    def read_logger(self, channel: int, sample_count: int | None = None) -> LoggerData:
        params = self.get_channel_params(channel)
        count = sample_count if sample_count is not None else params.logger_samples
        count = max(0, min(int(count), MAX_LOGGER_BLOCKS * SAMPLES_PER_BLOCK))
        if count == 0:
            return LoggerData(channel=channel, header=LoggerHeader(), samples=[])

        blocks = max(1, (count + SAMPLES_PER_BLOCK - 1) // SAMPLES_PER_BLOCK)
        raw_samples: list[bytes] = []
        for b in range(min(blocks, MAX_LOGGER_BLOCKS)):
            try:
                data = self.get_logger_block(channel, b)
            except ValueError:
                if b == 0:
                    raise
                break  # later block NAK → return what we have
            payload = data
            if len(data) >= 3 and data[0] == channel:
                payload = data[3:]
            for i in range(SAMPLES_PER_BLOCK):
                o = i * 8
                if o + 8 > len(payload):
                    break
                raw_samples.append(payload[o : o + 8])

        header = LoggerHeader()
        measure_records = raw_samples
        # Manual: first 3 records = header. FW 2.08 (Ident h) often stores U/I/C from sample 0.
        if len(raw_samples) >= 3 and not self._logger_records_look_like_uic(raw_samples[:3]):
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
            if len(h2) >= 8:
                header.capacity_mAh = capacity_from_digits(u32(h2, 2))
                header.charge_mA = current_from_digits(u16(h2, 6)) or 0
            if len(h3) >= 8:
                header.battery_type = h3[0] if h3[0] else header.battery_type
                header.cells = h3[1] if h3[1] else header.cells
                header.discharge_mA = current_from_digits(u16(h3, 2)) or 0
                header.forming_mA = current_from_digits(u16(h3, 4)) or 0
                header.pause_s = u16(h3, 6)
            # Fill program/type from channel params when header omitted on wire
            measure_records = raw_samples[3:]
        else:
            header = LoggerHeader(
                battery_slot=params.battery_slot,
                program=params.program,
                battery_type=params.battery_type,
                cells=params.cells,
                capacity_mAh=params.capacity_mAh,
                charge_mA=params.charge_mA,
                discharge_mA=params.discharge_mA,
                forming_mA=params.forming_mA,
                pause_s=params.pause_s,
            )

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

    @staticmethod
    def _logger_records_look_like_uic(records: list[bytes]) -> bool:
        """True when records look like voltage/current/capacity, not the 3-record header."""
        ok = 0
        for rec in records:
            if len(rec) < 8:
                return False
            u = u16(rec, 0)
            i = u16(rec, 2)
            if u == INVALID_MEASURE:
                continue
            # Plausible pack voltage 0.05 V … 60 V
            if 50 <= u <= 60000 and (i == INVALID_MEASURE or i < 200_000):
                ok += 1
        return ok >= 2
