"""Wire simulator for ALC 3000 PC (ChargeEasy Teil 2)."""

from __future__ import annotations

import time

from app.protocol.alc3000 import models as wire
from app.protocol.alc3000.constants import DB_SLOTS, IDENT_3000, SAMPLES_PER_BLOCK
from app.protocol.alc3000.framing import build_frame, parse_frame
from app.protocol.models import BatteryDbEntry, ChannelParams, DeviceParamsG, DeviceParamsH, DeviceParamsJ
from app.protocol.units import (
    capacity_to_digits,
    current_to_digits,
    pack_u16,
    pack_u32,
    temp_to_digits,
    voltage_to_digits,
)
from app.devices.profiles import DEVICES
from app.services.sim_physics import (
    SimTemperatures,
    channel_thermal_mode,
    clamp_battery_type,
    clamp_process_currents,
    idle_measurement,
    initial_stage,
    simulate_channel,
)

_MODEL = "alc3000_pc"
_ALLOWED_BT = DEVICES[_MODEL].battery_type_ids


class Alc3000Simulator:
    """Single-channel STX simulator for ALC 3000 PC."""

    def __init__(self) -> None:
        self.channel_count = 1
        self.channels = [
            ChannelParams(channel=0, battery_type=0x01, cells=4, capacity_mAh=2000, full_factor=250)
        ]
        self.running = [False]
        self.t0 = [0.0]
        self.db = [
            BatteryDbEntry(slot=i, name=f"Akku{i+1}", battery_type=0x01, cells=4, capacity_mAh=2000, full_factor=250)
            for i in range(DB_SLOTS)
        ]
        self.g = DeviceParamsG()
        self.h = DeviceParamsH()
        self.j = DeviceParamsJ()
        self._logger: list[bytes] = []
        self._temps = SimTemperatures()
        self.ident = (IDENT_3000 + "ALC3000").ljust(9)[:9]
        self.serial_number = "SIM-ALC3000"
        self.firmware = "Alc3000 Sim 1.0"

    def transfer(self, frame: bytes, timeout: float = 2.0) -> bytes:
        payload = parse_frame(frame)
        if not payload:
            return build_frame(bytes([0x04]))
        return build_frame(self._dispatch(payload[0], payload[1:]))

    def _dispatch(self, cmd: int, data: bytes) -> bytes:
        c = chr(cmd)
        if c == "p":
            return bytes([ord("p")]) + self._encode_params(self.channels[0])
        if c == "P":
            p = wire.decode_channel_params(data)
            p.channel = 0
            p.full_factor = 250
            p.charge_mA, p.discharge_mA = clamp_process_currents(
                _MODEL, 0, p.charge_mA, p.discharge_mA
            )
            p.battery_type = clamp_battery_type(p.battery_type, _ALLOWED_BT)
            if not self.running[0]:
                self.channels[0] = p
            return bytes([ord("p")]) + self._encode_params(self.channels[0])
        if c == "a":
            return bytes([ord("a"), 0x00, 0x00, self.channels[0].stage])
        if c == "A":
            stop = bool(data[1]) if len(data) > 1 else False
            if stop:
                self.running[0] = False
                self.channels[0].stage = 0x00
                self.channels[0].program = 0x00
            else:
                self.running[0] = True
                self.t0[0] = time.time()
                self.channels[0].stage = initial_stage(self.channels[0].program)
                self._seed_logger()
            return bytes([ord("a"), 0x00, 0x01 if stop else 0x00, self.channels[0].stage])
        if c == "m":
            return bytes([ord("m")]) + self._meas()
        if c == "t":
            ch0 = self.channels[0]
            charging, discharging = channel_thermal_mode(self.running[0], ch0.stage)
            bat, psu, sink = self._temps.sample(charging=charging, discharging=discharging)
            return (
                bytes([ord("t")])
                + pack_u16(temp_to_digits(bat))
                + pack_u16(temp_to_digits(psu))
                + pack_u16(temp_to_digits(sink))
            )
        if c == "d":
            slot = min(data[0] if data else 0, DB_SLOTS - 1)
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
        if c == "h":
            return bytes([ord("h")]) + self.h.encode()
        if c == "H":
            self.h = DeviceParamsH.decode(data)
            return bytes([ord("h")]) + self.h.encode()
        if c == "j":
            return bytes([ord("j")]) + self.j.encode()
        if c == "J":
            self.j = DeviceParamsJ.decode(data)
            return bytes([ord("j")]) + self.j.encode()
        if c == "L":
            self._logger = []
            self.channels[0].logger_samples = 0
            return bytes([ord("l"), 0x00])
        if c == "v":
            block = (data[1] << 8) | data[2] if len(data) >= 3 else 0
            return bytes([ord("v"), 0x00, data[1] if len(data) > 1 else 0, data[2] if len(data) > 2 else 0]) + self._logger_block(
                block
            )
        if c == "u":
            # firmware + serial (simplified)
            fw = self.firmware.encode("ascii", errors="replace")[:10].ljust(10, b"\x00")
            sn = self.serial_number.encode("ascii", errors="replace")[:10].ljust(10, b"\x00")
            return bytes([ord("u")]) + fw + pack_u16(0) + sn
        return bytes([0x04])

    def _encode_params(self, p: ChannelParams) -> bytes:
        return wire.encode_channel_set(p) + pack_u16(p.logger_samples) + bytes([p.stage & 0xFF])

    def _simulate(self) -> tuple[float, float, float]:
        p = self.channels[0]
        v, i, cap, stage, finished = simulate_channel(
            p.program,
            p.cells,
            p.charge_mA,
            p.discharge_mA,
            p.capacity_mAh,
            time.time() - self.t0[0],
            battery_type=p.battery_type,
            full_factor=p.full_factor,
        )
        p.stage = stage
        if finished:
            self.running[0] = False
        return v, i, cap

    def _meas(self) -> bytes:
        p = self.channels[0]
        if self.running[0]:
            v, i, cap = self._simulate()
        else:
            v, i, cap = idle_measurement(p.cells, p.battery_type)
        return pack_u16(voltage_to_digits(v)) + pack_u16(current_to_digits(i) if i else 0) + pack_u32(
            capacity_to_digits(cap)
        )

    def _seed_logger(self) -> None:
        p = self.channels[0]
        records: list[bytes] = []
        records.append(bytes([p.battery_slot & 0xFF, p.program & 0xFF, 0, 0, 12, 17, 7, 26]))
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
                pack_u16(voltage_to_digits(v)) + pack_u16(current_to_digits(i)) + pack_u32(capacity_to_digits(cap))
            )
        self._logger = records
        p.logger_samples = len(records)

    def _logger_block(self, block: int) -> bytes:
        records = self._logger
        if not records:
            self._seed_logger()
            records = self._logger
        start = block * SAMPLES_PER_BLOCK
        chunk = records[start : start + SAMPLES_PER_BLOCK]
        while len(chunk) < SAMPLES_PER_BLOCK:
            chunk.append(pack_u16(0) + pack_u16(0xFFFF) + pack_u32(0))
        return b"".join(chunk)
