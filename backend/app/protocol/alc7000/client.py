"""High-level ALC 7000 API — Wire wie pyALC7T, Oberfläche wie Dashboard-Client."""

from __future__ import annotations

from typing import Any, Protocol

from app.protocol.alc7000.mapping import (
    KSTAT_AKTIV,
    STAGE_CHARGE,
    STAGE_DISCHARGE,
    STAGE_IDLE,
    STRR_ENTLADEN,
    STRR_LADEN,
    battery_from_7000,
    battery_to_7000,
    program_from_7000,
    program_to_7000,
)
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
from app.services.sim_physics import idle_measurement


class Alc7000Link(Protocol):
    def com_string(self, befehl: str) -> str: ...

    def com_data(
        self,
        befehl: str,
        kanal_1based: int,
        param: int = 0,
        param_len: int = 0,
        ack: bool = False,
    ) -> Any: ...


class Alc7000Client:
    """Befehlsschicht über das historische ALC-7000-RS-232-Protokoll."""

    def __init__(self, link: Alc7000Link) -> None:
        self.link = link

    # ——— Low-level (Quelle) ———

    def read_ident(self) -> str:
        return self.link.com_string("v")

    def read_version(self) -> str:
        return self.link.com_string("V")

    def identify(self) -> str:
        try:
            return f"{self.read_ident()}|{self.read_version()}"
        except Exception:
            return self.read_ident()

    def read_progr(self, kanal_1based: int) -> int:
        return int(self.link.com_data("f", kanal_1based, 0, 0, False))

    def read_anz_zellen(self, kanal_1based: int) -> int:
        return int(self.link.com_data("u", kanal_1based, 0, 0, False))

    def read_ilad(self, kanal_1based: int) -> float:
        return float(self.link.com_data("i", kanal_1based, 0, 0, False)) / 1000.0

    def read_ientl(self, kanal_1based: int) -> float:
        return float(self.link.com_data("e", kanal_1based, 0, 0, False)) / 1000.0

    def read_cnenn(self, kanal_1based: int) -> float:
        return float(self.link.com_data("k", kanal_1based, 0, 0, False)) / 100.0

    def read_aktyp(self, kanal_1based: int) -> int:
        return int(self.link.com_data("t", kanal_1based, 0, 0, False))

    def read_mess(self, kanal_1based: int) -> list[int]:
        r = self.link.com_data("w", kanal_1based, 0, 0, False)
        if not isinstance(r, list) or len(r) != 3:
            raise ValueError("Messwerte ungültig")
        return [int(r[0]), int(r[1]), int(r[2])]

    def read_kan_status(self, kanal_1based: int) -> int:
        return int(self.link.com_data("a", kanal_1based, 0, 0, False))

    def read_ak_status(self, kanal_1based: int) -> int:
        return int(self.link.com_data("s", kanal_1based, 0, 0, False))

    def read_irichtg(self, kanal_1based: int) -> int:
        return int(self.link.com_data("h", kanal_1based, 0, 0, False))

    def write_progr(self, kanal_1based: int, programm: int) -> None:
        self.link.com_data("F", kanal_1based, programm, 1, True)

    def write_anz_zellen(self, kanal_1based: int, n: int) -> None:
        self.link.com_data("U", kanal_1based, n, 1, True)

    def write_aktyp(self, kanal_1based: int, aktyp: int) -> None:
        self.link.com_data("T", kanal_1based, aktyp, 1, True)

    def write_kan_aktivieren(self, kanal_1based: int, aktion: int) -> None:
        self.link.com_data("A", kanal_1based, aktion, 1, True)

    def write_ilad(self, kanal_1based: int, ilad_A: float) -> None:
        self.link.com_data("I", kanal_1based, int(round(ilad_A * 1000)), 2, True)

    def write_ientl(self, kanal_1based: int, ientl_A: float) -> None:
        self.link.com_data("E", kanal_1based, int(round(ientl_A * 1000)), 2, True)

    def write_cnenn(self, kanal_1based: int, cnenn_Ah: float) -> None:
        self.link.com_data("K", kanal_1based, int(round(cnenn_Ah * 100)), 2, True)

    # ——— Dashboard-API ———

    def _k(self, channel_0based: int) -> int:
        return channel_0based + 1

    def _stage_for(self, kanal_1based: int) -> int:
        aktiv = self.read_kan_status(kanal_1based)
        if aktiv != KSTAT_AKTIV:
            return STAGE_IDLE
        richtg = self.read_irichtg(kanal_1based)
        if richtg == STRR_ENTLADEN:
            return STAGE_DISCHARGE
        if richtg == STRR_LADEN:
            return STAGE_CHARGE
        # aktiv ohne Richtung: Programm ansehen
        prog = self.read_progr(kanal_1based)
        if prog in (1, 2, 3):  # Entladen / Entl-Laden / Test
            return STAGE_DISCHARGE
        return STAGE_CHARGE

    def get_channel_params(self, channel: int) -> ChannelParams:
        k = self._k(channel)
        prog7000 = self.read_progr(k)
        akku = self.read_aktyp(k)
        logger_n = 0
        link = self.link
        if hasattr(link, "engine"):
            logger_n = len(link.engine.channels[channel].logger)  # type: ignore[attr-defined]
        return ChannelParams(
            channel=channel,
            battery_slot=0x28,
            battery_type=battery_from_7000(akku),
            cells=self.read_anz_zellen(k),
            discharge_mA=self.read_ientl(k) * 1000.0,
            charge_mA=self.read_ilad(k) * 1000.0,
            capacity_mAh=self.read_cnenn(k) * 1000.0,
            program=program_from_7000(prog7000),
            forming_mA=0.0,
            pause_s=0,
            flags=0,
            full_factor=250,
            logger_samples=logger_n,
            stage=self._stage_for(k),
        )

    def set_channel_params(self, params: ChannelParams) -> ChannelParams:
        k = self._k(params.channel)
        # Nur im Leerlauf programmieren (wie Gerät neu startet bei Änderungen)
        if self.read_kan_status(k) != KSTAT_AKTIV:
            self.write_progr(k, program_to_7000(params.program))
            self.write_anz_zellen(k, max(1, int(params.cells)))
            self.write_aktyp(k, battery_to_7000(params.battery_type))
            self.write_ilad(k, max(0.05, params.charge_mA / 1000.0))
            self.write_ientl(k, max(0.05, params.discharge_mA / 1000.0))
            self.write_cnenn(k, max(0.01, params.capacity_mAh / 1000.0))
        return self.get_channel_params(params.channel)

    def get_activity(self, channel: int) -> ActivityState:
        k = self._k(channel)
        return ActivityState(channel=channel, action=0, stage=self._stage_for(k))

    def set_activity(self, channel: int, stop: bool = False) -> ActivityState:
        k = self._k(channel)
        self.write_kan_aktivieren(k, 0 if stop else 1)
        # Kurz auf Status warten (Quelle pollt in Schleife)
        for _ in range(10):
            st = self.read_kan_status(k)
            if (stop and st == 0) or (not stop and st == 1):
                break
        return ActivityState(channel=channel, action=0x01 if stop else 0x00, stage=self._stage_for(k))

    def get_measurements(self) -> list[ChannelMeasurement]:
        out: list[ChannelMeasurement] = []
        for ch in range(4):
            k = self._k(ch)
            try:
                u, i, c = self.read_mess(k)
            except Exception:
                out.append(ChannelMeasurement(channel=ch, voltage_V=0.0, current_mA=0.0, capacity_mAh=0.0))
                continue
            aktiv = self.read_kan_status(k) == KSTAT_AKTIV
            if not aktiv:
                cells = max(1, self.read_anz_zellen(k))
                bt = battery_from_7000(self.read_aktyp(k))
                v, i, cap = idle_measurement(cells, bt)
                out.append(
                    ChannelMeasurement(
                        channel=ch,
                        voltage_V=round(v, 3),
                        current_mA=i,
                        capacity_mAh=cap,
                    )
                )
            else:
                current = float(i)  # Digits = A·1000 → numerisch mA
                if self.read_irichtg(k) == STRR_ENTLADEN:
                    current = -abs(current)
                out.append(
                    ChannelMeasurement(
                        channel=ch,
                        voltage_V=u / 1000.0,
                        current_mA=current,
                        capacity_mAh=c * 10.0,  # C Digits/100 = Ah → mAh = Digits·10
                    )
                )
        return out

    def get_temperatures(self) -> Temperatures:
        # Probe / UI: kein Sensor — Identifikation reicht für Connect-Check
        self.read_ident()
        return Temperatures(battery_C=None, psu_C=None, heatsink_C=None)

    def get_battery_db(self, slot: int) -> BatteryDbEntry:
        raise NotImplementedError("Akku-Datenbank nicht am ALC 7000 Expert")

    def set_battery_db(self, entry: BatteryDbEntry) -> BatteryDbEntry:
        raise NotImplementedError("Akku-Datenbank nicht am ALC 7000 Expert")

    def get_device_g(self) -> DeviceParamsG:
        raise NotImplementedError("Chemie-Parameter nicht am ALC 7000 Expert")

    def set_device_g(self, params: DeviceParamsG) -> DeviceParamsG:
        raise NotImplementedError("Chemie-Parameter nicht am ALC 7000 Expert")

    def get_device_h(self) -> DeviceParamsH:
        raise NotImplementedError("Chemie-Parameter nicht am ALC 7000 Expert")

    def set_device_h(self, params: DeviceParamsH) -> DeviceParamsH:
        raise NotImplementedError("Chemie-Parameter nicht am ALC 7000 Expert")

    def get_device_j(self) -> DeviceParamsJ:
        raise NotImplementedError("Chemie-Parameter nicht am ALC 7000 Expert")

    def set_device_j(self, params: DeviceParamsJ) -> DeviceParamsJ:
        raise NotImplementedError("Chemie-Parameter nicht am ALC 7000 Expert")

    def clear_logger(self, channel: int) -> None:
        link = self.link
        if hasattr(link, "engine"):
            link.engine.channels[channel].logger = []  # type: ignore[attr-defined]

    def read_logger(self, channel: int, sample_count: int | None = None) -> LoggerData:
        params = self.get_channel_params(channel)
        samples: list[LoggerSample] = []
        link = self.link
        if hasattr(link, "engine"):
            samples = list(link.engine.channels[channel].logger)  # type: ignore[attr-defined]
        if sample_count is not None:
            samples = samples[:sample_count]
        header = LoggerHeader(
            battery_slot=params.battery_slot,
            program=params.program,
            battery_type=params.battery_type,
            cells=params.cells,
            capacity_mAh=params.capacity_mAh,
            charge_mA=params.charge_mA,
            discharge_mA=params.discharge_mA,
            forming_mA=0,
            pause_s=0,
        )
        return LoggerData(channel=channel, header=header, samples=samples)
