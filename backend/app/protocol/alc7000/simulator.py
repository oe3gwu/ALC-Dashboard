"""ALC 7000 Expert Simulator — spricht das echte Wire-Protokoll (com_string/com_data)."""

from __future__ import annotations

from typing import Any

from app.protocol.alc7000.engine import CHANNEL_COUNT, Alc7000Engine
from app.protocol.alc7000.framing import ACK


class Alc7000Simulator:
    """Transport-kompatibel zu Alc7000SerialLink (com_string / com_data)."""

    def __init__(self) -> None:
        self.engine = Alc7000Engine()
        self.serial_number = self.engine.serial_number
        self.firmware = self.engine.firmware

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    @property
    def is_open(self) -> bool:
        return True

    def com_string(self, befehl: str) -> str:
        if befehl == "v":
            return self.engine.ident
        if befehl == "V":
            return self.engine.version
        raise ValueError(f"Unbekannter String-Befehl {befehl!r}")

    def com_data(
        self,
        befehl: str,
        kanal_1based: int,
        param: int = 0,
        param_len: int = 0,
        ack: bool = False,
    ) -> Any:
        ch = kanal_1based - 1
        if ch < 0 or ch >= CHANNEL_COUNT:
            raise ValueError(f"Kanal {kanal_1based} ungültig")
        st = self.engine.channels[ch]
        e = self.engine

        # Writes (ACK)
        if ack:
            if befehl == "F":
                st.program = param & 0xFF
            elif befehl == "U":
                st.cells = max(1, min(20, param & 0xFF))
            elif befehl == "T":
                st.akku_typ = 1 if param else 0
            elif befehl == "A":
                e.activate(ch, 1 if param else 0)
            elif befehl == "I":
                e.set_charge_mA(ch, float(param))
            elif befehl == "E":
                e.set_discharge_mA(ch, float(param))
            elif befehl == "K":
                st.capacity_Ah = max(0.01, param / 100.0)
            else:
                raise ValueError(f"Unbekannter Write-Befehl {befehl!r}")
            return ACK

        # Reads
        if befehl == "f":
            return st.program
        if befehl == "u":
            return st.cells
        if befehl == "i":
            return int(round(st.charge_A * 1000))
        if befehl == "e":
            return int(round(st.discharge_A * 1000))
        if befehl == "k":
            return int(round(st.capacity_Ah * 100))
        if befehl == "t":
            return st.akku_typ
        if befehl == "a":
            return st.kan_status
        if befehl == "s":
            return st.ak_status
        if befehl == "h":
            return st.i_richtg
        if befehl == "w":
            u, i, c = e.measure(ch)
            return [u, i, c]
        raise ValueError(f"Unbekannter Read-Befehl {befehl!r}")
