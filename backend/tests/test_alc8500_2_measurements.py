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
