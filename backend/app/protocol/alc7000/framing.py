"""ALC 7000 Expert RS-232 framing (Wire-kompatibel zu alc7t / pyALC7T).

Protokollherkunft: Kommunikationsverhalten aus alc7t.bas (Frank Steinberg 2006)
bzw. pyALC7T/alcrs232.py (Joachim Siebold), GPLv2 — hier neu implementiert.
"""

from __future__ import annotations

STX = 0x02
ETX = 0x03
ESC = 0x05
ACK = 0x06

BAUDRATE = 9600
PARITY = "E"
BYTESIZE = 8
STOPBITS = 1


def encode_byte(b: int) -> bytes:
    """Escape 0x02 / 0x03 / 0x05 wie im historischen PC-Protokoll."""
    b &= 0xFF
    if b in (STX, ETX, ESC):
        return bytes([ESC, (b + 0x10) & 0xFF])
    return bytes([b])


def build_data_request(cmd: str, channel_0based: int, param: int, param_len: int) -> bytes:
    """STX | cmd | enc(ch) | enc(param…) | ETX — Kanal 0-basiert im Frame."""
    if len(cmd) != 1:
        raise ValueError("Befehl muss ein Zeichen sein")
    out = bytearray([STX, ord(cmd)])
    out.extend(encode_byte(channel_0based & 0xFF))
    if param_len == 0:
        out.append(0x00)
        out.append(0x00)
    elif param_len == 1:
        out.extend(encode_byte(param & 0xFF))
        out.append(0x00)
    elif param_len == 2:
        hibyte = (param >> 8) & 0xFF
        lobyte = param & 0xFF
        out.extend(encode_byte(hibyte))
        out.extend(encode_byte(lobyte))
    else:
        raise ValueError("param_len muss 0, 1 oder 2 sein")
    out.append(ETX)
    return bytes(out)


def build_string_request(cmd: str) -> bytes:
    if len(cmd) != 1:
        raise ValueError("Befehl muss ein Zeichen sein")
    return bytes([STX, ord(cmd), ETX])


def decode_escaped_payload(raw: bytes) -> bytes:
    """Payload zwischen STX und ETX mit Escape auflösen."""
    out = bytearray()
    escape = False
    for b in raw:
        if escape:
            out.append((b - 0x10) & 0xFF)
            escape = False
            continue
        if b == ESC:
            escape = True
            continue
        if b == ETX:
            break
        out.append(b)
    return bytes(out)
