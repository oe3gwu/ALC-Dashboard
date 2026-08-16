"""Power off the machine that runs the dashboard (appliance host)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable, Iterator
from typing import Any

log = logging.getLogger("elv-alc")

WhichFn = Callable[[str], str | None]
RunFn = Callable[..., Any]

POWEROFF_CANDIDATES: tuple[list[str], ...] = (
    ["systemctl", "poweroff", "--no-wall"],
    ["sudo", "-n", "systemctl", "poweroff", "--no-wall"],
    ["shutdown", "-h", "now"],
    ["sudo", "-n", "shutdown", "-h", "now"],
)


def iter_poweroff_argv(which: WhichFn | None = None) -> Iterator[list[str]]:
    finder = which or shutil.which
    seen: set[tuple[str, ...]] = set()
    for argv in POWEROFF_CANDIDATES:
        if not finder(argv[0]):
            continue
        key = tuple(argv)
        if key in seen:
            continue
        seen.add(key)
        yield list(argv)
    if not seen:
        raise FileNotFoundError("Kein systemctl/shutdown gefunden")


def resolve_poweroff_argv(which: WhichFn | None = None) -> list[str]:
    return next(iter_poweroff_argv(which))


def poweroff_host(
    argv: list[str] | None = None,
    *,
    which: WhichFn | None = None,
    run: RunFn | None = None,
) -> list[str]:
    """Run poweroff and raise if every candidate fails (e.g. missing polkit)."""
    runner = run or subprocess.run
    commands = [argv] if argv else list(iter_poweroff_argv(which))
    last_err = "Herunterfahren nicht erlaubt"
    for cmd in commands:
        log.warning("Host poweroff: %s", " ".join(cmd))
        try:
            proc = runner(cmd, capture_output=True, text=True, timeout=20)
        except FileNotFoundError as exc:
            last_err = str(exc)
            continue
        except subprocess.TimeoutExpired:
            last_err = "Zeitüberschreitung beim Herunterfahren"
            continue
        code = getattr(proc, "returncode", 1)
        if code == 0:
            return cmd
        err = (getattr(proc, "stderr", None) or getattr(proc, "stdout", None) or "").strip()
        last_err = err or f"exit {code}"
        log.warning("poweroff failed (%s): %s", " ".join(cmd), last_err)
    raise PermissionError(last_err)
