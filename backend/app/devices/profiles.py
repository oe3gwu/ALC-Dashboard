"""Device capability profiles for supported / listed ALC models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeviceFeatures:
    logger: bool = True
    battery_db: bool = True
    chemistry_params: bool = True
    chemistry_hj: bool = True  # h/H + j/J (8500-2); not in ELVjournal 8000/8500
    full_factor: bool = True  # Maximale Ladung / Vollfaktor (8500-2 wire byte)
    activator: bool = False
    activator_channel: int | None = None  # 0-based; e.g. 1 = channel 2
    ri_usb: bool = False
    firmware_guided: bool = True


@dataclass(frozen=True)
class DeviceProfile:
    id: str
    label: str
    enabled: bool
    channel_count: int
    protocol: str  # alc8500_usb | alc8xxx_usb | alc3000_usb | alc5000_usb | alc7000_rs232 | none
    battery_type_ids: tuple[int, ...]
    program_ids: tuple[int, ...]
    features: DeviceFeatures = field(default_factory=DeviceFeatures)
    baudrate: int = 38400
    # serial: 8E1 for 8500 USB, alc8xxx, and ALC 7000 RS-232
    parity: str = "E"
    bytesize: int = 8
    stopbits: int = 1
    disabled_reason: str = ""

    @property
    def simulator_label(self) -> str:
        return f"{self.label} Simulator · ×10 Zeit"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "enabled": self.enabled,
            "channel_count": self.channel_count,
            "protocol": self.protocol,
            "simulator_label": self.simulator_label,
            "disabled_reason": self.disabled_reason,
            "baudrate": self.baudrate,
            "features": {
                "logger": self.features.logger,
                "battery_db": self.features.battery_db,
                "chemistry_params": self.features.chemistry_params,
                "chemistry_hj": self.features.chemistry_hj,
                "full_factor": self.features.full_factor,
                "activator": self.features.activator,
                "activator_channel": self.features.activator_channel,
                "ri_usb": self.features.ri_usb,
                "firmware_guided": self.features.firmware_guided,
            },
            "battery_type_ids": list(self.battery_type_ids),
            "program_ids": list(self.program_ids),
        }


_NO_PROTO = "Protokoll nicht öffentlich dokumentiert"
_PROTO_DOCUMENTED = "Protokoll dokumentiert, noch nicht implementiert"

# Full 8500-2 chemistry / program sets (protocol bytes)
_BT_8500_2 = (0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08)
_PROG_ALL = (0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08)
_BT_7000 = (0x00, 0x01, 0x04)  # NiCd, NiMH, Pb (Gerät: NiCd/NiMH=0, Pb=1)
# Dashboard-Program-IDs, die auf 7000 0..5 gemappt werden
_PROG_7000 = (0x01, 0x02, 0x03, 0x04, 0x07, 0x08)
# ELVjournal 8000/8500 Expert: NiCd…Pb only
_BT_8XXX = (0x00, 0x01, 0x02, 0x03, 0x04)
_BT_3000 = (0x00, 0x01, 0x02, 0x03, 0x04, 0x05)  # + LiFePO (ChargeEasy)


# Reihenfolge: Modellnummer aufsteigend (1800 → 9000)
DEVICES: dict[str, DeviceProfile] = {
    "alc1800_pc": DeviceProfile(
        id="alc1800_pc",
        label="ALC 1800 PC",
        enabled=False,
        channel_count=0,
        protocol="none",
        battery_type_ids=(),
        program_ids=(),
        features=DeviceFeatures(
            logger=False,
            battery_db=False,
            chemistry_params=False,
            chemistry_hj=False,
            full_factor=False,
            activator=False,
            ri_usb=False,
            firmware_guided=False,
        ),
    ),
    "alc3000_pc": DeviceProfile(
        id="alc3000_pc",
        label="ALC 3000 PC",
        enabled=True,
        channel_count=1,
        protocol="alc3000_usb",
        battery_type_ids=_BT_3000,
        program_ids=_PROG_ALL,
        features=DeviceFeatures(
            logger=True,
            battery_db=True,
            chemistry_params=True,
            chemistry_hj=True,
            full_factor=False,
            activator=False,
            ri_usb=False,
            firmware_guided=True,
        ),
        baudrate=38400,
        parity="E",
    ),
    "alc5000_mobile": DeviceProfile(
        id="alc5000_mobile",
        label="ALC 5000 Mobile",
        enabled=True,
        channel_count=2,  # assumed (PDF: printed − 1; range 00–03)
        protocol="alc5000_usb",
        battery_type_ids=_BT_3000,
        program_ids=_PROG_ALL,
        features=DeviceFeatures(
            logger=True,
            battery_db=True,
            chemistry_params=True,
            chemistry_hj=True,
            full_factor=True,
            activator=True,
            ri_usb=False,
            firmware_guided=True,
        ),
        baudrate=38400,
        parity="E",
    ),
    "alc7000_expert": DeviceProfile(
        id="alc7000_expert",
        label="ALC 7000 Expert",
        enabled=True,
        channel_count=4,
        protocol="alc7000_rs232",
        battery_type_ids=_BT_7000,
        program_ids=_PROG_7000,
        features=DeviceFeatures(
            logger=True,
            battery_db=False,
            chemistry_params=False,
            chemistry_hj=False,
            full_factor=False,
            activator=False,
            ri_usb=False,
            firmware_guided=False,
        ),
        baudrate=9600,
        parity="E",
    ),
    "alc8000": DeviceProfile(
        id="alc8000",
        label="ALC 8000 Plus",
        enabled=True,
        channel_count=3,
        protocol="alc8xxx_usb",
        battery_type_ids=_BT_8XXX,
        program_ids=_PROG_ALL,
        features=DeviceFeatures(
            logger=False,
            battery_db=True,
            chemistry_params=True,
            chemistry_hj=False,
            full_factor=False,
            activator=True,
            activator_channel=1,
            ri_usb=False,
            firmware_guided=True,
        ),
        baudrate=38400,
        parity="E",
    ),
    "alc8500_expert": DeviceProfile(
        id="alc8500_expert",
        label="ALC 8500 Expert",
        enabled=True,
        channel_count=4,
        protocol="alc8xxx_usb",
        battery_type_ids=_BT_8XXX,
        program_ids=_PROG_ALL,
        features=DeviceFeatures(
            logger=True,
            battery_db=True,
            chemistry_params=True,
            chemistry_hj=False,
            full_factor=False,
            activator=True,
            activator_channel=1,
            ri_usb=False,
            firmware_guided=True,
        ),
        baudrate=38400,
        parity="E",
    ),
    "alc8500_2_expert": DeviceProfile(
        id="alc8500_2_expert",
        label="ALC 8500-2 Expert",
        enabled=True,
        channel_count=4,
        protocol="alc8500_usb",
        battery_type_ids=_BT_8500_2,
        program_ids=_PROG_ALL,
        features=DeviceFeatures(
            logger=True,
            battery_db=True,
            chemistry_params=True,
            chemistry_hj=True,
            full_factor=True,
            activator=True,
            activator_channel=1,
            ri_usb=False,
            firmware_guided=True,
        ),
        baudrate=38400,
        parity="E",
    ),
    "alc9000": DeviceProfile(
        id="alc9000",
        label="ALC 9000",
        enabled=False,
        channel_count=0,
        protocol="none",
        battery_type_ids=(),
        program_ids=(),
        features=DeviceFeatures(
            logger=False,
            battery_db=False,
            chemistry_params=False,
            chemistry_hj=False,
            full_factor=False,
            activator=False,
            ri_usb=False,
            firmware_guided=False,
        ),
    ),
}

DEFAULT_DEVICE_MODEL = "alc8500_2_expert"


def get_profile(device_id: str | None) -> DeviceProfile:
    if device_id and device_id in DEVICES:
        return DEVICES[device_id]
    return DEVICES[DEFAULT_DEVICE_MODEL]


def _device_sort_key(profile: DeviceProfile) -> tuple[int, int]:
    """Sortierung nach Modellnummer, 8500-2 nach 8500 Expert."""
    m = re.search(r"(\d+)", profile.id)
    num = int(m.group(1)) if m else 0
    variant = 1 if "_2_" in profile.id else 0
    return (num, variant)


def list_devices() -> list[dict[str, Any]]:
    ordered = sorted(DEVICES.values(), key=_device_sort_key)
    return [p.to_dict() for p in ordered]
