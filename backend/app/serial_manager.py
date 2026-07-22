from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import serial
from serial.tools import list_ports

from app.config import AppConfig
from app.devices.profiles import DeviceProfile, get_profile
from app.protocol.alc7000.client import Alc7000Client
from app.protocol.alc7000.link import Alc7000SerialLink
from app.protocol.alc7000.simulator import Alc7000Simulator
from app.protocol.alc3000.client import Alc3000Client
from app.protocol.alc3000.simulator import Alc3000Simulator
from app.protocol.alc5000.client import Alc5000Client, UnsupportedAlc5000Error
from app.protocol.alc5000.simulator import Alc5000Simulator
from app.protocol.alc8xxx.client import Alc8xxxClient
from app.protocol.alc8xxx.constants import IDENT_8000_PLUS, IDENT_8500
from app.protocol.alc8xxx.simulator import Alc8xxxSimulator
from app.protocol.commands import ProtocolClient
from app.protocol.constants import BAUDRATE, BYTESIZE, PARITY, STOPBITS
from app.protocol.framing import extract_frames as alc8500_extract_frames
from app.protocol.alc8500_2.simulator import Alc8500_2Simulator

log = logging.getLogger(__name__)

ClientType = ProtocolClient | Alc7000Client | Alc8xxxClient | Alc3000Client | Alc5000Client


class SerialIoActivity:
    """Monotonic TX/RX pulse counters for real serial traffic (UI LEDs)."""

    __slots__ = ("_lock", "tx_seq", "rx_seq")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tx_seq = 0
        self.rx_seq = 0

    def note_tx(self) -> None:
        with self._lock:
            self.tx_seq += 1

    def note_rx(self) -> None:
        with self._lock:
            self.rx_seq += 1

    def reset(self) -> None:
        with self._lock:
            self.tx_seq = 0
            self.rx_seq = 0

    def snapshot(self) -> tuple[int, int]:
        with self._lock:
            return self.tx_seq, self.rx_seq


@dataclass
class PortInfo:
    device: str
    description: str
    hwid: str
    vid: int | None = None
    pid: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "description": self.description,
            "hwid": self.hwid,
            "vid": f"{self.vid:04X}" if self.vid is not None else None,
            "pid": f"{self.pid:04X}" if self.pid is not None else None,
        }


class SerialTransport:
    """USB/STX-Transport für ALC 8500-2."""

    def __init__(self, port: str, baudrate: int = BAUDRATE, parity: str = PARITY, bytesize: int = BYTESIZE, stopbits: int = STOPBITS) -> None:
        self.port = port
        self.baudrate = baudrate
        self.parity = parity
        self.bytesize = bytesize
        self.stopbits = stopbits
        self._ser: serial.Serial | None = None
        self._lock = threading.RLock()
        self._buf = bytearray()
        self._extract = alc8500_extract_frames
        self.activity: SerialIoActivity | None = None

    def open(self) -> None:
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=0.05,
            write_timeout=2.0,
        )
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None

    @property
    def is_open(self) -> bool:
        return bool(self._ser and self._ser.is_open)

    def transfer(self, frame: bytes, timeout: float = 2.0) -> bytes:
        with self._lock:
            if not self._ser or not self._ser.is_open:
                raise RuntimeError("Serielle Schnittstelle nicht geöffnet")
            self._ser.reset_input_buffer()
            self._buf.clear()
            self._ser.write(frame)
            self._ser.flush()
            if self.activity:
                self.activity.note_tx()
            deadline = time.monotonic() + timeout
            saw_rx = False
            while time.monotonic() < deadline:
                chunk = self._ser.read(256)
                if chunk:
                    if self.activity and not saw_rx:
                        self.activity.note_rx()
                        saw_rx = True
                    self._buf.extend(chunk)
                    frames, self._buf = self._extract(self._buf)
                    if frames:
                        return frames[0]
                else:
                    time.sleep(0.01)
            raise TimeoutError(f"Keine Antwort von {self.port} innerhalb {timeout}s")


class SerialManager:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self._lock = threading.RLock()
        self._transport: Any = None
        self._client: ClientType | None = None
        self.connected_port: str | None = None
        self.simulator = False
        self.device_model: str = cfg.device_model
        self.last_error: str | None = None
        self._io_activity = SerialIoActivity()
        self._last_auto_probed: list[str] = []
        # Retry connect after boot until success; cleared by API disconnect only
        self.startup_autoconnect = True

    @property
    def mock(self) -> bool:
        """Legacy-Alias für simulator."""
        return self.simulator

    @property
    def profile(self) -> DeviceProfile:
        return get_profile(self.cfg.device_model)

    def list_ports(self) -> list[PortInfo]:
        ports: list[PortInfo] = []
        for p in list_ports.comports():
            ports.append(
                PortInfo(
                    device=p.device,
                    description=p.description or "",
                    hwid=p.hwid or "",
                    vid=p.vid,
                    pid=p.pid,
                )
            )
        return ports

    def _score_port(self, info: PortInfo) -> int:
        score = 0
        profile = self.profile
        for hint in self.cfg.usb_hints:
            try:
                if info.vid is not None and info.pid is not None:
                    if f"{info.vid:04X}".upper() == hint.vendor_id.upper() and f"{info.pid:04X}".upper() == hint.product_id.upper():
                        score += 100
            except Exception:
                pass
        desc = (info.description + info.hwid).lower()
        if "elv" in desc or "alc" in desc or "cp210" in desc or "ftdi" in desc:
            score += 20
        if profile.protocol == "alc7000_rs232":
            if "ttyS" in info.device or "ttyUSB" in info.device:
                score += 10
        else:
            if "ttyUSB" in info.device or "ttyACM" in info.device:
                score += 5
        return score

    def auto_detect(self) -> str | None:
        candidates = sorted(self.list_ports(), key=self._score_port, reverse=True)
        probed: list[str] = []
        rs232 = self.profile.protocol == "alc7000_rs232"
        for info in candidates:
            # Platform ttyS* are slow/useless for USB ALC profiles and block the server
            if (not rs232) and "/ttyS" in info.device.replace("\\", "/"):
                continue
            if self._score_port(info) <= 0 and not info.device.startswith(("/dev/ttyUSB", "/dev/ttyACM", "/dev/ttyS")):
                continue
            if (not rs232) and info.device.startswith("/dev/ttyS"):
                continue
            probed.append(info.device)
            try:
                if self._probe(info.device):
                    # USB-Serial needs a brief settle before reopen in connect()
                    time.sleep(0.2)
                    self._last_auto_probed = probed
                    return info.device
            except Exception as exc:
                log.debug("Probe %s failed: %s", info.device, exc)
        self._last_auto_probed = probed
        return None

    def _probe(self, port: str) -> bool:
        profile = self.profile
        if profile.protocol == "alc7000_rs232":
            link = Alc7000SerialLink(port, profile.baudrate)
            try:
                link.open()
                client = Alc7000Client(link)
                client.read_ident()
                return True
            except Exception:
                return False
            finally:
                link.close()
        transport = SerialTransport(port, self.cfg.baudrate or profile.baudrate)
        try:
            transport.open()
            if profile.protocol == "alc8xxx_usb":
                client: Any = Alc8xxxClient(
                    transport,
                    channel_count=profile.channel_count,
                    has_logger=profile.features.logger,
                )
                client.get_temperatures()
            elif profile.protocol == "alc3000_usb":
                client = Alc3000Client(transport)
                client.get_temperatures()
            elif profile.protocol == "alc5000_usb":
                client5 = Alc5000Client(transport, channel_count=profile.channel_count)
                try:
                    client5.ensure_supported_device()
                except UnsupportedAlc5000Error:
                    return False
                client5.get_temperatures()
            else:
                # alc8500_usb and unknown USB STX profiles
                client = ProtocolClient(transport)
                client.get_temperatures()
            return True
        except Exception:
            return False
        finally:
            transport.close()

    def connect(self, port: str | None = None, use_simulator: bool | None = None, use_mock: bool | None = None) -> dict[str, Any]:
        with self._lock:
            self.disconnect()
            profile = self.profile
            if not profile.enabled:
                self.last_error = f"Gerät {profile.label} ist nicht verfügbar"
                raise RuntimeError(self.last_error)

            sim = self.cfg.simulator if use_simulator is None else use_simulator
            if use_mock is not None:
                sim = use_mock

            # Expliziter Port-Parameter hat Vorrang; bei Simulator gespeicherten Port ignorieren
            if port is not None:
                chosen_port = str(port).strip()
            elif sim:
                chosen_port = ""
            else:
                chosen_port = (self.cfg.serial_port or "").strip()

            # Port gesetzt → kein Simulator
            if chosen_port:
                sim = False

            self.device_model = profile.id

            if sim:
                return self._connect_simulator(profile)

            used_auto = not chosen_port
            chosen = chosen_port or self.auto_detect()
            if not chosen:
                probed = getattr(self, "_last_auto_probed", []) or []
                if probed:
                    self.last_error = (
                        f"Kein ALC-Gerät gefunden (geprüft: {', '.join(probed)})"
                    )
                else:
                    self.last_error = "Kein ALC-Gerät gefunden (keine seriellen Ports)"
                raise RuntimeError(self.last_error)

            if used_auto:
                time.sleep(0.05)

            self._io_activity.reset()

            if profile.protocol == "alc7000_rs232":
                link = Alc7000SerialLink(chosen, profile.baudrate)
                link.activity = self._io_activity
                link.open()
                client = Alc7000Client(link)
                ident = client.read_ident()
                try:
                    link.serial_number = ident
                    link.firmware = client.read_version()
                except Exception:
                    pass
                self._transport = link
                self._client = client
            elif profile.protocol == "alc8500_usb":
                transport = SerialTransport(chosen, self.cfg.baudrate or profile.baudrate)
                transport.activity = self._io_activity
                transport.open()
                client = ProtocolClient(transport)
                client.get_temperatures()
                self._transport = transport
                self._client = client
            elif profile.protocol == "alc8xxx_usb":
                transport = SerialTransport(chosen, self.cfg.baudrate or profile.baudrate)
                transport.activity = self._io_activity
                transport.open()
                client8 = Alc8xxxClient(
                    transport,
                    channel_count=profile.channel_count,
                    has_logger=profile.features.logger,
                )
                client8.get_temperatures()
                self._transport = transport
                self._client = client8
            elif profile.protocol == "alc3000_usb":
                transport = SerialTransport(chosen, self.cfg.baudrate or profile.baudrate)
                transport.activity = self._io_activity
                transport.open()
                client3 = Alc3000Client(transport)
                client3.get_temperatures()
                self._transport = transport
                self._client = client3
            elif profile.protocol == "alc5000_usb":
                transport = SerialTransport(chosen, self.cfg.baudrate or profile.baudrate)
                transport.activity = self._io_activity
                transport.open()
                client5 = Alc5000Client(transport, channel_count=profile.channel_count)
                try:
                    client5.ensure_supported_device()
                except UnsupportedAlc5000Error as e:
                    transport.close()
                    self.last_error = str(e)
                    raise RuntimeError(self.last_error) from e
                try:
                    transport.serial_number = client5.serial_number
                    transport.firmware = client5.firmware
                except Exception:
                    pass
                client5.get_temperatures()
                self._transport = transport
                self._client = client5
            else:
                raise RuntimeError(f"Kein Protokoll für {profile.label}")

            self.connected_port = chosen
            self.simulator = False
            self.last_error = None
            return self.status()

    def _connect_simulator(self, profile: DeviceProfile) -> dict[str, Any]:
        if profile.protocol == "alc7000_rs232":
            sim = Alc7000Simulator()
            self._transport = sim
            self._client = Alc7000Client(sim)
            self.connected_port = "simulator"
            self.simulator = True
            self.last_error = None
            return self.status()
        if profile.protocol == "alc8500_usb":
            sim8500 = Alc8500_2Simulator()
            self._transport = sim8500
            self._client = ProtocolClient(sim8500)
            self.connected_port = "simulator"
            self.simulator = True
            self.last_error = None
            return self.status()
        if profile.protocol == "alc8xxx_usb":
            prefix = IDENT_8000_PLUS if profile.id == "alc8000" else IDENT_8500
            sim8 = Alc8xxxSimulator(
                channel_count=profile.channel_count,
                has_logger=profile.features.logger,
                ident_prefix=prefix,
            )
            self._transport = sim8
            self._client = Alc8xxxClient(
                sim8,
                channel_count=profile.channel_count,
                has_logger=profile.features.logger,
            )
            self.connected_port = "simulator"
            self.simulator = True
            self.last_error = None
            return self.status()
        if profile.protocol == "alc3000_usb":
            sim3 = Alc3000Simulator()
            self._transport = sim3
            self._client = Alc3000Client(sim3)
            self.connected_port = "simulator"
            self.simulator = True
            self.last_error = None
            return self.status()
        if profile.protocol == "alc5000_usb":
            sim5 = Alc5000Simulator(channel_count=profile.channel_count)
            client5 = Alc5000Client(sim5, channel_count=profile.channel_count)
            client5.ensure_supported_device()
            self._transport = sim5
            self._client = client5
            self.connected_port = "simulator"
            self.simulator = True
            self.last_error = None
            return self.status()
        raise RuntimeError(f"Kein Simulator für {profile.label}")

    def disconnect(self) -> None:
        with self._lock:
            if isinstance(self._transport, (SerialTransport, Alc7000SerialLink)):
                self._transport.close()
            elif hasattr(self._transport, "close"):
                try:
                    self._transport.close()
                except Exception:
                    pass
            self._transport = None
            self._client = None
            self.connected_port = None
            self.simulator = False
            self._io_activity.reset()

    def mark_failed(self, exc: BaseException | str | None = None) -> None:
        """Drop a dead link, keep last_error, and allow 5s auto-reconnect.

        Unlike API disconnect, link loss re-enables startup_autoconnect so the
        boot retry loop can start again when the cable is plugged back in.
        """
        if isinstance(exc, BaseException):
            msg = str(exc).strip() or type(exc).__name__
        elif isinstance(exc, str) and exc.strip():
            msg = exc.strip()
        else:
            msg = "USB-Verbindung unterbrochen"
        low = msg.lower()
        if "usb" in low or "serial" in low or "verbindung" in low:
            self.last_error = msg
        else:
            self.last_error = f"USB-Verbindung unterbrochen ({msg})"
        self.startup_autoconnect = True
        self.disconnect()

    @property
    def client(self) -> ClientType:
        if not self._client:
            raise RuntimeError("Nicht verbunden")
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def status(self) -> dict[str, Any]:
        profile = get_profile(self.device_model or self.cfg.device_model)
        live_io = self.is_connected and not self.simulator
        tx_seq, rx_seq = self._io_activity.snapshot() if live_io else (0, 0)
        return {
            "connected": self.is_connected,
            "port": self.connected_port,
            "simulator": self.simulator,
            "mock": self.simulator,  # legacy
            "device_model": profile.id,
            "device_label": profile.label,
            "status_label": (
                profile.simulator_label
                if self.simulator and self.is_connected
                else (profile.label if self.is_connected else None)
            ),
            "last_error": self.last_error,
            "baudrate": profile.baudrate if profile.protocol == "alc7000_rs232" else self.cfg.baudrate,
            "channel_count": profile.channel_count,
            "tx_seq": tx_seq,
            "rx_seq": rx_seq,
        }

    def with_client(self):
        return self._lock

    def try_acquire(self) -> bool:
        """Non-blocking lock for live polls while logger holds the bus."""
        return self._lock.acquire(blocking=False)

    def release(self) -> None:
        self._lock.release()
