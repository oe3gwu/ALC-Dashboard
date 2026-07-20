"""ALC 8500-2 measurement formats: all-channel (sim) and per-channel (FW 2.08)."""

from __future__ import annotations

from app.protocol.alc8500_2.simulator import Alc8500_2Simulator
from app.protocol.commands import ProtocolClient
from app.protocol.framing import build_frame, extract_frames, parse_frame
from app.protocol.units import pack_u16, pack_u32, voltage_to_digits


class _ScriptedTransport:
    def __init__(self, replies: list[bytes]) -> None:
        self.replies = list(replies)
        self.sent: list[bytes] = []

    def transfer(self, frame: bytes, timeout: float = 2.0) -> bytes:
        self.sent.append(parse_frame(frame))
        if not self.replies:
            raise TimeoutError("no scripted reply")
        return self.replies.pop(0)


def _meas_frame(channel: int, voltage_V: float = 1.2, current_mA: float = 0.0, capacity_mAh: float = 0.0) -> bytes:
    payload = (
        bytes([ord("m"), channel & 0xFF])
        + pack_u16(voltage_to_digits(voltage_V))
        + pack_u16(int(round(current_mA * 10)))
        + pack_u32(int(round(capacity_mAh * 10000)))
    )
    return build_frame(payload)


def test_simulator_all_channel_measurements():
    client = ProtocolClient(Alc8500_2Simulator())
    ms = client.get_measurements()
    assert len(ms) == 4
    assert ms[0].voltage_V is not None and ms[0].voltage_V > 0


def test_per_channel_fw208_measurements():
    replies = [_meas_frame(ch, voltage_V=1.0 + ch * 0.1) for ch in range(4)]
    t = _ScriptedTransport(replies)
    client = ProtocolClient(t)
    ms = client.get_measurements()
    assert len(ms) == 4
    assert [round(m.voltage_V or 0, 1) for m in ms] == [1.0, 1.1, 1.2, 1.3]
    assert t.sent == [bytes([ord("m"), ch]) for ch in range(4)]


def test_bare_m_nak_then_not_used_when_per_channel_works():
    """First request is m+0; must not fall back to bare m if per-channel replies."""
    t = _ScriptedTransport([_meas_frame(0), _meas_frame(1), _meas_frame(2), _meas_frame(3)])
    ProtocolClient(t).get_measurements()
    assert all(len(s) == 2 and s[0] == ord("m") for s in t.sent)


def test_extract_frames_ignores_escaped_etx():
    # STX, 'p', ESC ETX (data 0x03), ETX  → one frame, payload p + 0x03
    buf = bytearray([0x02, ord("p"), 0x05, 0x13, 0x03, 0x02, ord("x"), 0x03])
    frames, rest = extract_frames(buf)
    assert len(frames) == 2
    assert parse_frame(frames[0]) == bytes([ord("p"), 0x03])
    assert parse_frame(frames[1]) == bytes([ord("x")])
    assert rest == bytearray()


def test_full_factor_off_wire_zero_maps_to_api_250():
    from app.protocol.models import ChannelParams

    core = ChannelParams(channel=2, cells=4, full_factor=250).encode_set()
    assert core[-1] == 0  # FW 2.08 wire off
    decoded = ChannelParams.decode(core + b"\x00\x00")  # + logger
    assert decoded.full_factor == 250


def test_parse_ident_u_fw208_ff_padding():
    from app.protocol.models import parse_ident_u

    # Real device shape: FW(10)=h   V2.08 + FFh, pad FFh FFh, SN WEQ1435528
    body = b"h   V2.08\xff" + b"\xff\xff" + b"WEQ1435528"
    fw, sn = parse_ident_u(body)
    assert fw.startswith("h")
    assert "2.08" in fw
    assert sn == "WEQ1435528"


def test_read_ident_u_simulator():
    client = ProtocolClient(Alc8500_2Simulator())
    fw, sn = client.read_ident_u()
    assert fw.startswith("h")
    assert sn
    assert client.firmware == fw
    assert client.serial_number == sn


def test_battery_db_encode_fw208_length():
    from app.protocol.models import BatteryDbEntry

    entry = BatteryDbEntry(slot=1, name="Test", battery_type=0x01, cells=4, capacity_mAh=2000, full_factor=90)
    assert len(entry.encode_fw208()) == 25
    assert len(entry.encode()) == 26


def test_battery_db_decode_fw208_auto_full_factor_90():
    """Real ALC 8500-2 FW 2.08 ``d`` payload for slot AUTO (Cap-first, flags|full|0xFF)."""
    from app.protocol.models import BatteryDbEntry

    raw = bytes.fromhex("004155544f20202020200302031975004e204e200000005aff")
    assert len(raw) == 25
    entry = BatteryDbEntry.decode(raw)
    assert entry.name == "AUTO"
    assert entry.battery_type == 0x03
    assert entry.cells == 2
    assert entry.capacity_mAh == 5200.0
    assert entry.charge_mA == 2000.0
    assert entry.discharge_mA == 2000.0
    assert entry.forming_mA == 0.0
    assert entry.full_factor == 90
