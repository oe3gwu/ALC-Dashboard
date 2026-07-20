"""Wire simulator for ALC 8500-2 Expert (STX/USB protocol)."""

from __future__ import annotations

import time

from app.devices.profiles import DEVICES
from app.protocol.framing import build_frame, parse_frame
from app.protocol.models import (
    BatteryDbEntry,
    ChannelParams,
    DeviceParamsG,
    DeviceParamsH,
    DeviceParamsJ,
)
from app.protocol.units import (
    capacity_to_digits,
    current_to_digits,
    pack_u16,
    pack_u32,
    temp_to_digits,
    voltage_to_digits,
)
from app.services.sim_physics import (
    SimTemperatures,
    channel_thermal_mode,
    clamp_battery_type,
    clamp_process_currents,
    idle_measurement,
    initial_stage,
    simulate_channel,
)

_MODEL = "alc8500_2_expert"
_ALLOWED_BT = DEVICES[_MODEL].battery_type_ids


class Alc8500_2Simulator:
    """Four-channel STX simulator for ALC 8500-2 Expert."""

    def __init__(self) -> None:
        self.channels = [ChannelParams(channel=i, battery_type=0x01, cells=4, capacity_mAh=2000) for i in range(4)]
        self.running = [False] * 4
        self.t0 = [0.0] * 4
        self.db = [
            BatteryDbEntry(slot=i, name=f"Akku{i+1}", battery_type=0x01, cells=4, capacity_mAh=2000)
            for i in range(40)
        ]
        self.g = DeviceParamsG()
        self.h = DeviceParamsH()
        self.j = DeviceParamsJ()
        self._logger: dict[int, list[bytes]] = {i: [] for i in range(4)}
        self._temps = SimTemperatures()
        self.serial_number = "SIM-8500-2"
        self.firmware = "Simulator 1.0"

    def transfer(self, frame: bytes, timeout: float = 2.0) -> bytes:
        payload = parse_frame(frame)
        if not payload:
            return build_frame(bytes([0x04]))
        cmd = payload[0]
        resp = self._dispatch(cmd, payload[1:])
        return build_frame(resp)

    def _dispatch(self, cmd: int, data: bytes) -> bytes:
        c = chr(cmd)
        if c == "p":
            ch = data[0] if data else 0
            return bytes([ord("p")]) + self._encode_params(self.channels[ch])
        if c == "P":
            p = ChannelParams.decode(data)
            p.charge_mA, p.discharge_mA = clamp_process_currents(
                _MODEL, p.channel, p.charge_mA, p.discharge_mA
            )
            p.battery_type = clamp_battery_type(p.battery_type, _ALLOWED_BT)
            if not self.running[p.channel]:
                self.channels[p.channel] = p
            return bytes([ord("p")]) + self._encode_params(self.channels[p.channel])
        if c == "a":
            ch = data[0] if data else 0
            return bytes([ord("a"), ch, 0x00 if not self.running[ch] else 0x00, self.channels[ch].stage])
        if c == "A":
            ch = data[0] if data else 0
            stop = bool(data[1]) if len(data) > 1 else False
            if stop:
                self.running[ch] = False
                self.channels[ch].stage = 0x00
                self.channels[ch].program = 0x00
            else:
                self.running[ch] = True
                self.t0[ch] = time.time()
                self.channels[ch].stage = initial_stage(self.channels[ch].program)
                self._seed_logger(ch)
            return bytes([ord("a"), ch, 0x01 if stop else 0x00, self.channels[ch].stage])
        if c == "m":
            return bytes([ord("m")]) + self._meas_all()
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
            slot = data[0] if data else 0
            return bytes([ord("d")]) + self.db[slot].encode()
        if c == "D":
            entry = BatteryDbEntry.decode(data)
            self.db[entry.slot] = entry
            return bytes([ord("d")]) + entry.encode()
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
        if c == "u":
            # Same layout as ChargeEasy Teil 2: FW(10) + pad(2) + SN(10)
            fw = (self.firmware or "h Sim 1.0").encode("ascii", errors="replace")[:10].ljust(10, b"\x00")
            # Prefer Ident-style field: prefix h + version text
            if not self.firmware.startswith("h"):
                fw = ("h " + (self.firmware or "Sim")).encode("ascii", errors="replace")[:10].ljust(10, b"\x00")
            sn = (self.serial_number or "SIM-8500-2").encode("ascii", errors="replace")[:10].ljust(10, b"\x00")
            return bytes([ord("u")]) + fw + b"\x00\x00" + sn
        if c == "L":
            ch = data[0] if data else 0
            self._logger[ch] = []
            self.channels[ch].logger_samples = 0
            return bytes([ord("l"), ch])
        if c == "v":
            ch = data[0] if data else 0
            block = (data[1] << 8) | data[2] if len(data) >= 3 else 0
            return bytes([ord("v"), ch, data[1] if len(data) > 1 else 0, data[2] if len(data) > 2 else 0]) + self._logger_block(
                ch, block
            )
        return bytes([0x04])

    def _encode_params(self, p: ChannelParams) -> bytes:
        base = p.encode_set()
        return base + pack_u16(p.logger_samples) + bytes([p.stage & 0xFF])

    def _simulate_channel(self, ch: int) -> tuple[float, float, float]:
        """Return (voltage_V, current_mA, capacity_mAh) and update stage."""
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
        for ch in range(4):
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
        start = block * 100
        chunk = records[start : start + 100]
        while len(chunk) < 100:
            chunk.append(pack_u16(0) + pack_u16(0xFFFF) + pack_u32(0))
        return b"".join(chunk)
