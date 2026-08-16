"""Host power-off command selection (does not actually shut down)."""

from __future__ import annotations

import pytest

from app.services.host_power import resolve_poweroff_argv, spawn_poweroff


def test_prefers_systemctl():
    def which(name: str) -> str | None:
        return "/usr/bin/systemctl" if name == "systemctl" else None

    assert resolve_poweroff_argv(which) == ["systemctl", "poweroff", "--no-wall"]


def test_falls_back_to_sudo_shutdown():
    def which(name: str) -> str | None:
        return "/usr/bin/sudo" if name == "sudo" else None

    assert resolve_poweroff_argv(which) == ["sudo", "-n", "systemctl", "poweroff", "--no-wall"]


def test_uses_shutdown_without_sudo_when_present():
    def which(name: str) -> str | None:
        if name == "shutdown":
            return "/sbin/shutdown"
        return None

    assert resolve_poweroff_argv(which) == ["shutdown", "-h", "now"]


def test_missing_tools_raise():
    with pytest.raises(FileNotFoundError):
        resolve_poweroff_argv(lambda _name: None)


def test_spawn_uses_resolved_argv():
    spawned: list[list[str]] = []

    def fake_popen(cmd: list[str], **_kwargs: object) -> None:
        spawned.append(cmd)

    out = spawn_poweroff(
        ["systemctl", "poweroff", "--no-wall"],
        popen=fake_popen,
    )
    assert out == ["systemctl", "poweroff", "--no-wall"]
    assert spawned == [out]
