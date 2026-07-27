"""Port listing includes udev aliases and dialout metadata."""

from __future__ import annotations

from app.config import AppConfig
from app.serial_manager import PortInfo, SerialManager, dialout_status


def test_list_ports_includes_udev_aliases(monkeypatch):
    cfg = AppConfig(device_model="alc8500_2_expert")
    mgr = SerialManager(cfg)

    class FakeComport:
        device = "/dev/ttyUSB0"
        description = "ALC 8500 Expert"
        hwid = "USB VID:PID=18EF:E030"
        vid = 0x18EF
        pid = 0xE030

    monkeypatch.setattr("app.serial_manager.list_ports.comports", lambda: [FakeComport()])
    monkeypatch.setattr(
        "glob.glob",
        lambda pattern: (
            ["/dev/elv-alc", "/dev/elv-alc8500", "/dev/elv-alc8xxx"]
            if pattern == "/dev/elv-alc*"
            else []
        ),
    )
    monkeypatch.setattr("os.path.islink", lambda p: p.startswith("/dev/elv-alc"))
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("os.path.realpath", lambda p: "/dev/ttyUSB0")
    monkeypatch.setattr("app.serial_manager._device_group_name", lambda p: "dialout")

    ports = mgr.list_ports()
    devices = {p.device: p for p in ports}
    assert "/dev/ttyUSB0" in devices
    assert devices["/dev/ttyUSB0"].kind == "serial"
    assert devices["/dev/ttyUSB0"].group == "dialout"
    assert "/dev/elv-alc" in devices
    assert devices["/dev/elv-alc"].kind == "udev"
    assert devices["/dev/elv-alc"].target == "/dev/ttyUSB0"
    assert "/dev/elv-alc8500" in devices
    assert "/dev/elv-alc8xxx" in devices


def test_dialout_status_shape():
    status = dialout_status()
    assert "user" in status
    assert "group_exists" in status
    assert "in_group" in status
    assert isinstance(status["group_members"], list)


def test_portinfo_to_dict_includes_kind():
    info = PortInfo(
        device="/dev/elv-alc",
        description="udev → ttyUSB0",
        hwid="",
        kind="udev",
        target="/dev/ttyUSB0",
        group="dialout",
    )
    d = info.to_dict()
    assert d["kind"] == "udev"
    assert d["target"] == "/dev/ttyUSB0"
    assert d["group"] == "dialout"
