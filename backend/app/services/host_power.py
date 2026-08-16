"""Power off the machine that runs the dashboard (appliance host)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

log = logging.getLogger("elv-alc")

WhichFn = Callable[[str], str | None]
PopenFn = Callable[..., Any]

POWEROFF_CANDIDATES: tuple[list[str], ...] = (
    ["systemctl", "poweroff", "--no-wall"],
    ["sudo", "-n", "systemctl", "poweroff", "--no-wall"],
    ["shutdown", "-h", "now"],
    ["sudo", "-n", "shutdown", "-h", "now"],
)


def resolve_poweroff_argv(which: WhichFn | None = None) -> list[str]:
    finder = which or shutil.which
    for argv in POWEROFF_CANDIDATES:
        if finder(argv[0]):
            return list(argv)
    raise FileNotFoundError("Kein systemctl/shutdown gefunden")


def spawn_poweroff(
    argv: list[str] | None = None,
    *,
    which: WhichFn | None = None,
    popen: PopenFn | None = None,
) -> list[str]:
    cmd = argv or resolve_poweroff_argv(which)
    log.warning("Host poweroff: %s", " ".join(cmd))
    runner = popen or subprocess.Popen
    runner(cmd, start_new_session=True)
    return cmd
