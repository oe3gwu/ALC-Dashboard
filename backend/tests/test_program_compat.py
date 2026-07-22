"""Chemistry/program pairs the ALC FW rejects with NAK on P."""

from app.protocol.constants import (
    program_compatible,
    program_incompatible_message,
)


def test_zyklen_ok_for_nimh():
    assert program_compatible(0x01, 0x07)
    assert program_incompatible_message(0x01, 0x07) is None


def test_zyklen_rejected_for_pb():
    assert not program_compatible(0x04, 0x07)
    msg = program_incompatible_message(0x04, 0x07)
    assert msg is not None
    assert "Zyklen" in msg
    assert "Pb" in msg


def test_formieren_auffrischen_rejected_for_li_and_pb():
    for prog in (0x06, 0x08):
        assert not program_compatible(0x04, prog)
        assert not program_compatible(0x03, prog)  # Li-4.2
    assert program_compatible(0x00, 0x06)  # NiCd Formieren
    assert program_compatible(0x07, 0x08)  # NiZn Auffrischen


def test_charge_ok_for_pb():
    assert program_compatible(0x04, 0x01)
    assert program_compatible(0x04, 0x03)
    assert program_compatible(0x04, 0x05)
