"""Serielle Verbindung ALC 7000 — Wire-Verhalten wie pyALC7T/alcrs232.py."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

import serial

if TYPE_CHECKING:
    from app.serial_manager import SerialIoActivity

from app.protocol.alc7000.framing import (
    ACK,
    BAUDRATE,
    BYTESIZE,
    ETX,
    PARITY,
    STOPBITS,
    STX,
    build_data_request,
    build_string_request,
)

log = logging.getLogger(__name__)

MAX_TIMEOUT_RETRY = 6
DEFAULT_TIMEOUT = 2.0


class Alc7000SerialLink:
    """RS-232 9600 8E1 mit com_string / com_data."""

    def __init__(self, port: str, baudrate: int = BAUDRATE) -> None:
        self.port = port
        self.baudrate = baudrate
        self._ser: serial.Serial | None = None
        self._lock = threading.RLock()
        self.serial_number: str | None = None
        self.firmware: str | None = None
        self.activity: SerialIoActivity | None = None

    def _note_tx(self) -> None:
        if self.activity:
            self.activity.note_tx()

    def _note_rx(self) -> None:
        if self.activity:
            self.activity.note_rx()

    def open(self) -> None:
        parity = serial.PARITY_EVEN if PARITY == "E" else serial.PARITY_NONE
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=BYTESIZE,
            parity=parity,
            stopbits=STOPBITS,
            timeout=DEFAULT_TIMEOUT,
            write_timeout=2.0,
            rtscts=False,
            dsrdtr=False,
        )
        time.sleep(0.5)
        try:
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
        except Exception:
            pass

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None

    @property
    def is_open(self) -> bool:
        return bool(self._ser and self._ser.is_open)

    def com_string(self, befehl: str) -> str:
        with self._lock:
            if not self._ser or not self._ser.is_open:
                raise RuntimeError("Serielle Schnittstelle nicht geöffnet")
            frame = build_string_request(befehl)
            self._ser.write(frame)
            self._note_tx()
            identifier = ""
            count = 0
            timeout_retry = 0
            saw_rx = False
            while True:
                c = self._ser.read(1)
                if c == b"":
                    timeout_retry += 1
                    if timeout_retry > MAX_TIMEOUT_RETRY:
                        raise TimeoutError("Timeout beim Lesen (String)")
                    continue
                if not saw_rx:
                    self._note_rx()
                    saw_rx = True
                timeout_retry = 0
                if c == bytes([ETX]):
                    break
                if c[0] < 32:
                    continue
                identifier += chr(c[0])
                count += 1
                if count > 20:
                    raise ValueError("String-Antwort zu lang")
            return identifier

    def com_data(
        self,
        befehl: str,
        kanal_1based: int,
        param: int = 0,
        param_len: int = 0,
        ack: bool = False,
    ) -> Any:
        with self._lock:
            if not self._ser or not self._ser.is_open:
                raise RuntimeError("Serielle Schnittstelle nicht geöffnet")
            try:
                self._ser.reset_input_buffer()
            except Exception:
                pass
            channel_0 = max(0, kanal_1based - 1)
            frame = build_data_request(befehl, channel_0, param, param_len)
            self._ser.write(frame)
            self._note_tx()

            if ack:
                return self._wait_ack(frame)

            # Auf STX der Antwort warten
            retry = 0
            timeout_retry = 0
            saw_rx = False
            while True:
                c = self._ser.read(1)
                if c == b"":
                    timeout_retry += 1
                    if timeout_retry > MAX_TIMEOUT_RETRY:
                        raise TimeoutError("Timeout beim Lesen (Daten)")
                    continue
                if not saw_rx:
                    self._note_rx()
                    saw_rx = True
                timeout_retry = 0
                if c == bytes([STX]):
                    break
                retry += 1
                if retry > MAX_TIMEOUT_RETRY:
                    raise ValueError("Keine STX-Antwort vom ALC 7000")

            # Payload bis ETX (mit Escape)
            s = bytearray()
            count = 0
            timeout_retry = 0
            escape = False
            while True:
                c = self._ser.read(1)
                if c == b"":
                    timeout_retry += 1
                    if timeout_retry > MAX_TIMEOUT_RETRY:
                        raise TimeoutError("Timeout beim Lesen (Payload)")
                    continue
                timeout_retry = 0
                b = c[0]
                if escape:
                    s.append((b - 0x10) & 0xFF)
                    escape = False
                    count += 1
                    if count > 6:
                        raise ValueError("Antwort zu lang")
                    continue
                if b == ETX:
                    break
                if b == 0x05:
                    escape = True
                    continue
                s.append(b)
                count += 1
                if count > 6:
                    raise ValueError("Antwort zu lang")

            if count == 1:
                return int(s[0])
            if count == 2:
                return int(s[0]) * 256 + int(s[1])
            if count == 6:
                return [
                    int(s[0]) * 256 + int(s[1]),
                    int(s[2]) * 256 + int(s[3]),
                    int(s[4]) * 256 + int(s[5]),
                ]
            raise ValueError(f"Unerwartete Antwortlänge {count}")

    def _wait_ack(self, frame: bytes) -> None:
        assert self._ser
        retry = 0
        timeout_retry = 0
        saw_rx = False
        while True:
            c = self._ser.read(1)
            if c == b"":
                timeout_retry += 1
                if timeout_retry > MAX_TIMEOUT_RETRY:
                    raise TimeoutError("Timeout auf ACK")
                continue
            if not saw_rx:
                self._note_rx()
                saw_rx = True
            timeout_retry = 0
            if c in (bytes([STX]), bytes([ETX])):
                continue
            if c == bytes([ACK]):
                return
            # Retry write like source
            self._ser.write(frame)
            self._note_tx()
            retry += 1
            if retry > 3:
                raise ValueError("Befehlsübermittlung fehlgeschlagen (kein ACK)")
