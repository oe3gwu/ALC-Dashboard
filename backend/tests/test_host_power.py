"""Host power-off command selection (does not actually shut down)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.host_power import poweroff_host, resolve_poweroff_argv


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


def test_poweroff_host_succeeds_on_zero():
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    out = poweroff_host(["systemctl", "poweroff", "--no-wall"], run=fake_run)
    assert out == ["systemctl", "poweroff", "--no-wall"]
    assert calls == [out]


def test_poweroff_host_tries_next_candidate_on_failure():
    calls: list[list[str]] = []

    def which(name: str) -> str | None:
        return "/bin/" + name if name in {"systemctl", "sudo"} else None

    def fake_run(cmd: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(cmd)
        if cmd[0] == "systemctl":
            return SimpleNamespace(returncode=1, stderr="Interactive authentication required", stdout="")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    out = poweroff_host(which=which, run=fake_run)
    assert calls[0] == ["systemctl", "poweroff", "--no-wall"]
    assert out == ["sudo", "-n", "systemctl", "poweroff", "--no-wall"]


def test_poweroff_host_raises_when_all_fail():
    def fake_run(_cmd: list[str], **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stderr="Access denied", stdout="")

    with pytest.raises(PermissionError, match="Access denied"):
        poweroff_host(["systemctl", "poweroff"], run=fake_run)
