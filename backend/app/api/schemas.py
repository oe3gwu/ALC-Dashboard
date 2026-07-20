from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    port: str | None = None
    simulator: bool | None = None
    mock: bool | None = None  # legacy alias for simulator


class ChannelParamsIn(BaseModel):
    channel: int = Field(ge=0, le=3)
    battery_slot: int = 0x28
    battery_type: int = 0x01
    cells: int = 1
    discharge_mA: float = 500
    charge_mA: float = 500
    capacity_mAh: float = 2000
    program: int = 0x01
    forming_mA: float = 0
    pause_s: int = 60
    flags: int = 0
    full_factor: int = 250
    activator: bool | None = None


class ActivityRequest(BaseModel):
    channel: int = Field(ge=0, le=3)
    stop: bool = False


class StartProcessRequest(BaseModel):
    params: ChannelParamsIn
    confirm: bool = False


class BatteryDbIn(BaseModel):
    slot: int = Field(ge=0, le=39)
    name: str = ""
    battery_type: int = 0x01
    cells: int = 1
    discharge_mA: float = 500
    charge_mA: float = 500
    capacity_mAh: float = 2000
    pause_s: int = 60
    forming_mA: float = 0
    flags: int = 0
    full_factor: int = 250


class DeviceGIn(BaseModel):
    discharge_NiCd_mV: int = 900
    discharge_NiMH_mV: int = 900
    discharge_LiIon_mV: int = 3000
    discharge_LiPo_mV: int = 3100
    discharge_Pb_mV: int = 1850
    pause_min: int = 1
    cycles_cycle_NiCd: int = 5
    cycles_cycle_NiMH: int = 5
    cycles_form_NiCd: int = 5
    cycles_form_NiMH: int = 5
    dU_NiCd: int = 40
    dU_NiMH: int = 20


class DeviceHIn(BaseModel):
    charge_LiIon_mV: int = 4100
    maintain_LiIon_mV: int = 4050
    charge_LiPo_mV: int = 4200
    maintain_LiPo_mV: int = 4150
    charge_Pb_mV: int = 2350
    maintain_Pb_mV: int = 2260


class DeviceJIn(BaseModel):
    discharge_LiFePO4_mV: int = 2300
    charge_LiFePO4_mV: int = 3650
    maintain_LiFePO4_mV: int = 3450
    illumination: int = 2
    alarm_beep: bool = False
    button_beep: bool = False
    contrast: int = 8


class ConfigUpdate(BaseModel):
    serial_port: str | None = None
    device_model: str | None = None
    simulator: bool | None = None
    mock: bool | None = None  # legacy → simulator
    poll_interval: float | None = None
    host: str | None = None
    port: int | None = None


class FirmwareGuideResponse(BaseModel):
    steps: list[str]
    warning: str
    filename_hint: str
    notes: list[str]


def channel_from_in(data: ChannelParamsIn):
    from app.protocol.constants import FLAG_ACTIVATOR
    from app.protocol.models import ChannelParams

    flags = data.flags
    if data.activator is True:
        flags |= FLAG_ACTIVATOR
    elif data.activator is False:
        flags &= ~FLAG_ACTIVATOR
    return ChannelParams(
        channel=data.channel,
        battery_slot=data.battery_slot,
        battery_type=data.battery_type,
        cells=data.cells,
        discharge_mA=data.discharge_mA,
        charge_mA=data.charge_mA,
        capacity_mAh=data.capacity_mAh,
        program=data.program,
        forming_mA=data.forming_mA,
        pause_s=data.pause_s,
        flags=flags,
        full_factor=data.full_factor,
    )


def diff_params(requested: dict[str, Any], echoed: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "charge_mA",
        "discharge_mA",
        "capacity_mAh",
        "cells",
        "battery_type",
        "program",
        "forming_mA",
        "pause_s",
        "full_factor",
        "flags",
    ]
    changed = {}
    for k in keys:
        if requested.get(k) != echoed.get(k):
            changed[k] = {"requested": requested.get(k), "device": echoed.get(k)}
    return changed
