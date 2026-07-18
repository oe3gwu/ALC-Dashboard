"""Wire simulator for ALC 8000 Plus / ALC 8500 Expert (ELVjournal protocol)."""

from __future__ import annotations

import time

from app.protocol.alc8xxx import models as wire
from app.protocol.alc8xxx.constants import (
    DB_SLOTS,
    IDENT_8000_PLUS,
    IDENT_8500,
    SAMPLES_PER_BLOCK,
)
from app.protocol.alc8xxx.framing import build_frame, parse_frame
from app.protocol.models import BatteryDbEntry, ChannelParams, DeviceParamsG
from app.protocol.units import (
    capacity_to_digits,
    current_to_digits,
    pack_u16,
    pack_u32,
    voltage_to_digits,
)
from app.devices.profiles import DEVICES
from app.services.sim_physics import (
    clamp_battery_type,
    clamp_process_currents,
    idle_measurement,
    initial_stage,
    simulate_channel,
)

_ALLOWED_BT = DEVICES["alc8500_expert"].battery_type_ids


class Alc8xxxSimulator:
    """STX/USB simulator speaking the alc8xxx wire protocol."""

    def __init__(
        self,
        *,
        channel_count: int = 4,
        has_logger: bool = True,
        ident_prefix: str = IDENT_8500,
    ) -> None:
        self.channel_count = max(1, min(4, channel_count))
        self.has_logger = has_logger
        self.ident_prefix = (ident_prefix or IDENT_8500)[:1]
        self.device_model = "alc8500_expert" if self.ident_prefix == IDENT_8500 else "alc8000"
        self.channels = [
            ChannelParams(channel=i, battery_type=0x01, cells=4, capacity_mAh=2000, full_factor=250)
            for i in range(self.channel_count)
        ]
        self.running = [False] * self.channel_count
        self.t0 = [0.0] * self.channel_count
        self.db = [
            BatteryDbEntry(slot=i, name=f"Akku{i+1}", battery_type=0x01, cells=4, capacity_mAh=2000, full_factor=250)
            for i in range(DB_SLOTS)
        ]
        self.g = DeviceParamsG()
        self._logger: dict[int, list[bytes]] = {i: [] for i in range(self.channel_count)}
        model = "8500Ex" if self.ident_prefix == IDENT_8500 else "8000Pl"
        # 9 ASCII bytes, first letter = variant
        self.ident = (self.ident_prefix + model).ljust(9)[:9]
        self.serial_number = f"SIM-{model}"
        self.firmware = "Alc8xxx Sim 1.0"

    def transfer(self, frame: bytes, timeout: float = 2.0) -> bytes:
        payload = parse_frame(frame)
        if not payload:
            return build_frame(bytes([0x04]))
        resp = self._dispatch(payload[0], payload[1:])
        return build_frame(resp)

    def _dispatch(self, cmd: int, data: bytes) -> bytes:
        c = chr(cmd)
        if c == "p":
            ch = data[0] if data else 0
            ch = min(ch, self.channel_count - 1)
            return bytes([ord("p")]) + self._encode_params(self.channels[ch])
        if c == "P":
            p = wire.decode_channel_params(data)
            if p.channel >= self.channel_count:
                p.channel = self.channel_count - 1
            p.charge_mA, p.discharge_mA = clamp_process_currents(
                self.device_model, p.channel, p.charge_mA, p.discharge_mA
            )
            p.battery_type = clamp_battery_type(p.battery_type, _ALLOWED_BT)
            p.full_factor = 250
            if not self.running[p.channel]:
                self.channels[p.channel] = p
            return bytes([ord("p")]) + self._encode_params(self.channels[p.channel])
        if c == "a":
            ch = data[0] if data else 0
            ch = min(ch, self.channel_count - 1)
            return bytes([ord("a"), ch, 0x00, self.channels[ch].stage])
        if c == "A":
            ch = data[0] if data else 0
            ch = min(ch, self.channel_count - 1)
            stop = bool(data[1]) if len(data) > 1 else False
            if stop:
                self.running[ch] = False
                self.channels[ch].stage = 0x00
                self.channels[ch].program = 0x00
            else:
                self.running[ch] = True
                self.t0[ch] = time.time()
                self.channels[ch].stage = initial_stage(self.channels[ch].program)
                if self.has_logger:
                    self._seed_logger(ch)
            return bytes([ord("a"), ch, 0x01 if stop else 0x00, self.channels[ch].stage])
        if c == "m":
            return bytes([ord("m")]) + self._meas_all()
        if c == "t":
            return bytes([ord("t")]) + pack_u16(2500) + pack_u16(3200) + pack_u16(2800)
        if c == "d":
            slot = data[0] if data else 0
            slot = min(slot, DB_SLOTS - 1)
            return bytes([ord("d")]) + wire.encode_battery_db(self.db[slot])
        if c == "D":
            entry = wire.decode_battery_db(data)
            entry.full_factor = 250
            if 0 <= entry.slot < DB_SLOTS:
                self.db[entry.slot] = entry
            return bytes([ord("d")]) + wire.encode_battery_db(self.db[entry.slot])
        if c == "g":
            return bytes([ord("g")]) + self.g.encode()
        if c == "G":
            self.g = DeviceParamsG.decode(data)
            return bytes([ord("g")]) + self.g.encode()
        if c == "L":
            if not self.has_logger:
                return bytes([0x04])
            ch = data[0] if data else 0
            ch = min(ch, self.channel_count - 1)
            self._logger[ch] = []
            self.channels[ch].logger_samples = 0
            return bytes([ord("l"), ch])
        if c == "v":
            if not self.has_logger:
                return bytes([0x04])
            ch = data[0] if data else 0
            ch = min(ch, self.channel_count - 1)
            block = (data[1] << 8) | data[2] if len(data) >= 3 else 0
            return (
                bytes([ord("v"), ch, data[1] if len(data) > 1 else 0, data[2] if len(data) > 2 else 0])
                + self._logger_block(ch, block)
            )
        return bytes([0x04])

    def _encode_params(self, p: ChannelParams) -> bytes:
        return wire.encode_channel_set(p) + pack_u16(p.logger_samples) + bytes([p.stage & 0xFF])

    def _simulate_channel(self, ch: int) -> tuple[float, float, float]:
        p = self.channels[ch]
        v, i, cap, stage, finished = simulate_channel(
            p.program,
            p.cells,
            p.charge_mA,
            p.discharge_mA,
            p.capacity_mAh,
            time.time() - self.t0[ch],
            battery_type=p.battery_type,
            full_factor=p.full_factor,
        )
        p.stage = stage
        if finished:
            self.running[ch] = False
        return v, i, cap

    def _meas_all(self) -> bytes:
        out = bytearray()
        for ch in range(self.channel_count):
            p = self.channels[ch]
            if self.running[ch]:
                v, i, cap = self._simulate_channel(ch)
            else:
                v, i, cap = idle_measurement(p.cells, p.battery_type)
            out += pack_u16(voltage_to_digits(v))
            out += pack_u16(current_to_digits(i) if i else 0)
            out += pack_u32(capacity_to_digits(cap))
        return bytes(out)

    def _seed_logger(self, ch: int) -> None:
        if not self.has_logger:
            return
        p = self.channels[ch]
        records: list[bytes] = []
        records.append(
            bytes(
                [
                    p.battery_slot & 0xFF,
                    p.program & 0xFF,
                    0,
                    0,
                    12,
                    17,
                    7,
                    26,
                ]
            )
        )
        records.append(
            bytes([p.battery_type & 0xFF, p.cells & 0xFF])
            + pack_u32(capacity_to_digits(p.capacity_mAh))
            + pack_u16(current_to_digits(p.charge_mA))
        )
        records.append(
            bytes([p.battery_type & 0xFF, p.cells & 0xFF])
            + pack_u16(current_to_digits(p.discharge_mA))
            + pack_u16(current_to_digits(p.forming_mA))
            + pack_u16(p.pause_s)
        )
        for n in range(120):
            v = 1.2 * p.cells + n * 0.002
            i = p.charge_mA
            cap = n * (p.charge_mA * 5 / 3600)
            records.append(
                pack_u16(voltage_to_digits(v))
                + pack_u16(current_to_digits(i))
                + pack_u32(capacity_to_digits(cap))
            )
        self._logger[ch] = records
        p.logger_samples = len(records)

    def _logger_block(self, ch: int, block: int) -> bytes:
        records = self._logger.get(ch, [])
        if not records:
            self._seed_logger(ch)
            records = self._logger[ch]
        start = block * SAMPLES_PER_BLOCK
        chunk = records[start : start + SAMPLES_PER_BLOCK]
        while len(chunk) < SAMPLES_PER_BLOCK:
            chunk.append(pack_u16(0) + pack_u16(0xFFFF) + pack_u32(0))
        return b"".join(chunk)
