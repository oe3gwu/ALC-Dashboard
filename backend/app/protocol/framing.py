from __future__ import annotations

from .constants import ESC, ESCAPE_MAP, ETX, STX, UNESCAPE_MAP


class FrameError(ValueError):
    pass


def escape_payload(payload: bytes) -> bytes:
    out = bytearray()
    for b in payload:
        if b in ESCAPE_MAP:
            out.extend(ESCAPE_MAP[b])
        else:
            out.append(b)
    return bytes(out)


def unescape_payload(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == ESC:
            if i + 1 >= len(data):
                raise FrameError("Unvollständige Escape-Sequenz")
            mapped = UNESCAPE_MAP.get(data[i + 1])
            if mapped is None:
                raise FrameError(f"Ungültige Escape-Sequenz: 05 {data[i + 1]:02X}")
            out.append(mapped)
            i += 2
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


def build_frame(payload: bytes) -> bytes:
    return bytes([STX]) + escape_payload(payload) + bytes([ETX])


def parse_frame(frame: bytes) -> bytes:
    if len(frame) < 2:
        raise FrameError("Frame zu kurz")
    if frame[0] != STX:
        raise FrameError(f"Erwarte STX, bekam {frame[0]:02X}")
    if frame[-1] != ETX:
        raise FrameError(f"Erwarte ETX, bekam {frame[-1]:02X}")
    return unescape_payload(frame[1:-1])


def extract_frames(buffer: bytearray) -> tuple[list[bytes], bytearray]:
    """Extract complete STX…ETX frames from a stream buffer.

    ETX after ESC is data (escaped), not a frame terminator.
    """
    frames: list[bytes] = []
    while True:
        try:
            start = buffer.index(STX)
        except ValueError:
            buffer.clear()
            break
        if start > 0:
            del buffer[:start]
        end: int | None = None
        i = 1
        while i < len(buffer):
            b = buffer[i]
            if b == ESC:
                if i + 1 >= len(buffer):
                    # Incomplete escape — wait for more bytes
                    end = None
                    break
                i += 2
                continue
            if b == ETX:
                end = i
                break
            i += 1
        if end is None:
            break
        frame = bytes(buffer[: end + 1])
        del buffer[: end + 1]
        frames.append(frame)
    return frames, buffer
