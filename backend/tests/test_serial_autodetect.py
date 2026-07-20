"""Serial auto-detect scoring and probe dispatch (no hardware)."""

from __future__ import annotations

from app.config import AppConfig, UsbHint
from app.serial_manager import PortInfo, SerialManager


def test_score_prefers_elv_18ef_e030():
    cfg = AppConfig(
        device_model="alc8500_2_expert",
        usb_hints=[
            UsbHint(vendor_id="0403", product_id="F06E"),
            UsbHint(vendor_id="18EF", product_id="E030"),
        ],
    )
    mgr = SerialManager(cfg)
    elv = PortInfo(device="/dev/ttyUSB0", description="CP210x", hwid="USB VID:PID=18EF:E030", vid=0x18EF, pid=0xE030)
    generic = PortInfo(device="/dev/ttyUSB1", description="CP2102", hwid="USB VID:PID=10C4:EA60", vid=0x10C4, pid=0xEA60)
    assert mgr._score_port(elv) > mgr._score_port(generic)
    assert mgr._score_port(elv) >= 100


def test_auto_detect_error_lists_probed_ports(monkeypatch):
    cfg = AppConfig(device_model="alc8500_2_expert", simulator=False, serial_port="")
    mgr = SerialManager(cfg)
    ports = [
        PortInfo(device="/dev/ttyUSB0", description="x", hwid="", vid=None, pid=None),
        PortInfo(device="/dev/ttyUSB1", description="y", hwid="", vid=None, pid=None),
    ]
    monkeypatch.setattr(mgr, "list_ports", lambda: ports)
    monkeypatch.setattr(mgr, "_probe", lambda port: False)
    try:
        mgr.connect(port="", use_simulator=False)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        msg = str(exc)
        assert "Kein ALC-Gerät gefunden" in msg
        assert "/dev/ttyUSB0" in msg
        assert "/dev/ttyUSB1" in msg
