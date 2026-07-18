"""Wire simulator for ALC 5000 Mobile (Ident j, FW > 2.00)."""

from __future__ import annotations

import time

from app.protocol.alc5000 import models as wire
from app.protocol.alc5000.constants import (
    A_STOP,
    CHANNEL_COUNT,
    DB_SLOTS,
    IDENT_5000_FW2,
    PROG_TO_A_START,
    SAMPLES_PER_BLOCK,
)

_A_START_TO_PROG = {v: k for k, v in PROG_TO_A_START.items()}
from app.protocol.alc5000.framing import build_frame, parse_frame
from app.protocol.models import BatteryDbEntry, ChannelParams, DeviceParamsG, DeviceParamsH, DeviceParamsJ
from app.protocol.units import (
    capacity_to_digits,
    current_to_digits,
    pack_u16,
    pack_u32,
    voltage_to_digits,
)
from app.services.sim_physics import idle_measurement, initial_stage, simulate_channel


class Alc5000Simulator:
    """Two-channel STX simulator for ALC 5000 Mobile (Ident j)."""

    def __init__(self, channel_count: int = CHANNEL_COUNT) -> None:
        self.channel_count = channel_count
        self.channels = [
            ChannelParams(channel=i, battery_type=0x01, cells=4, capacity_mAh=2000, full_factor=100)
            for i in range(channel_count)
        ]
        self.running = [False] * channel_count
        self.t0 = [0.0] * channel_count
        self.db = [
            BatteryDbEntry(
                slot=i, name=f"Akku{i+1}", battery_type=0x01, cells=4, capacity_mAh=2000, full_factor=100
            )
            for i in range(DB_SLOTS)
        ]
        self.g = DeviceParamsG()
        # unused = LowBat Speiseakku (mV) — PDF: only relevant for 5000 Mobile
        self.h = DeviceParamsH(unused=10500)
        self.j = DeviceParamsJ()
        self._logger: dict[int, list[bytes]] = {i: [] for i in range(channel_count)}
        # FW field must start with Ident j (PDF connect gate)
        self.firmware = (IDENT_5000_FW2 + "2.10     ")[:10]
        self.serial_number = "SIM-ALC5000"
        self.rtc = (0, 0, 12, 17, 7, 26)  # sec,min,hour,day,month,year

    def transfer(self, frame: bytes, timeout: float = 2.0) -> bytes:
        payload = parse_frame(frame)
        if not payload:
            return build_frame(bytes([0x04]))
        return build_frame(self._dispatch(payload[0], payload[1:]))

    def _ch(self, data: bytes, default: int = 0) -> int:
        ch = data[0] if data else default
        return max(0, min(ch, self.channel_count - 1))

    def _dispatch(self, cmd: int, data: bytes) -> bytes:
        c = chr(cmd)
        if c == "p":
            ch = self._ch(data)
            return bytes([ord("p")]) + wire.encode_channel_read(self.channels[ch])
        if c == "P":
            p = wire.decode_channel_params(data)
            ch = max(0, min(p.channel, self.channel_count - 1))
            p.channel = ch
            if not self.running[ch]:
                self.channels[ch] = p
            return bytes([ord("p")]) + wire.encode_channel_read(self.channels[ch])
        if c == "a":
            ch = self._ch(data)
            return bytes([ord("a"), ch, self.channels[ch].stage & 0xFF])
        if c == "A":
            ch = self._ch(data)
            action = data[1] if len(data) > 1 else A_STOP
            if action == A_STOP:
                self.running[ch] = False
                self.channels[ch].stage = 0x00
                self.channels[ch].program = 0x00
            else:
                self.running[ch] = True
                self.t0[ch] = time.time()
                # Map A start code back to program if channel still idle program
                if self.channels[ch].program in (0x00,):
                    self.channels[ch].program = _A_START_TO_PROG.get(action, 0x01)
                self.channels[ch].stage = initial_stage(self.channels[ch].program)
                self._seed_logger(ch)
            return bytes([ord("a"), ch, self.channels[ch].stage & 0xFF])
        if c == "m":
            ch = self._ch(data)
            return bytes([ord("m"), ch]) + self._meas(ch)
        if c == "t":
            return bytes([ord("t")]) + pack_u16(2500) + pack_u16(3200) + pack_u16(2800)
        if c == "d":
            slot = min(data[0] if data else 0, DB_SLOTS - 1)
            return bytes([ord("d")]) + wire.encode_battery_db(self.db[slot])
        if c == "D":
            entry = wire.decode_battery_db(data)
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
            ch = self._ch(data)
            self._logger[ch] = []
            self.channels[ch].logger_samples = 0
            return bytes([ord("l"), ch])
        if c == "v":
            ch = self._ch(data)
            block = (data[1] << 8) | data[2] if len(data) >= 3 else 0
            return bytes([ord("v"), ch, data[1] if len(data) > 1 else 0, data[2] if len(data) > 2 else 0]) + self._logger_block(
                ch, block
            )
        if c == "u":
            fw = self.firmware.encode("ascii", errors="replace")[:10].ljust(10, b"\x00")
            sn = self.serial_number.encode("ascii", errors="replace")[:10].ljust(10, b"\x00")
            return bytes([ord("u")]) + fw + pack_u16(0) + sn
        if c == "c":
            return bytes([ord("c")]) + wire.encode_rtc(*self.rtc)
        if c == "C":
            self.rtc = wire.decode_rtc(data)
            return bytes([ord("c")]) + wire.encode_rtc(*self.rtc)
        return bytes([0x04])

    def _simulate(self, ch: int) -> tuple[float, float, float]:
        p = self.channels[ch]
        v, i, cap, stage = simulate_channel(
            p.program,
            p.cells,
            p.charge_mA,
            p.discharge_mA,
            p.capacity_mAh,
            time.time() - self.t0[ch],
        )
        p.stage = stage
        return v, i, cap

    def _meas(self, ch: int) -> bytes:
        if self.running[ch]:
            v, i, cap = self._simulate(ch)
        else:
            v, i, cap = idle_measurement(self.channels[ch].cells)
        return pack_u16(voltage_to_digits(v)) + pack_u16(current_to_digits(i) if i else 0) + pack_u32(
            capacity_to_digits(cap)
        )

    def _seed_logger(self, ch: int) -> None:
        p = self.channels[ch]
        sec, minute, hour, day, month, year = self.rtc
        records: list[bytes] = []
        # Header with RTC fields (PDF: only 5000 Mobile outputs clock in logger header)
        records.append(bytes([p.battery_slot & 0xFF, p.program & 0xFF, sec, minute, hour, day, month, year]))
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
        self._logger[ch] = records
        p.logger_samples = len(records)

    def _logger_block(self, ch: int, block: int) -> bytes:
        records = self._logger.get(ch) or []
        if not records:
            self._seed_logger(ch)
            records = self._logger[ch]
        start = block * SAMPLES_PER_BLOCK
        chunk = records[start : start + SAMPLES_PER_BLOCK]
        while len(chunk) < SAMPLES_PER_BLOCK:
            chunk.append(pack_u16(0) + pack_u16(0xFFFF) + pack_u32(0))
        return b"".join(chunk)
