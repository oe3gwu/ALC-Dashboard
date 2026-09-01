"""Installer must keep an existing device config.yaml on update."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parents[2] / "scripts" / "install-systemd.sh"
UNINSTALLER = Path(__file__).resolve().parents[2] / "scripts" / "uninstall-systemd.sh"


def test_installer_excludes_existing_config_yaml() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert 'if [[ -f "$DEST/config.yaml" ]]; then' in text
    assert "--exclude 'config.yaml'" in text
    assert "Bestehende Gerätekonfiguration bleibt erhalten" in text


def test_installer_cleans_up_legacy_alc_user() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert 'LEGACY_USER="alc"' in text
    assert 'systemctl stop "$SERVICE_NAME"' in text
    assert 'rm -f /etc/polkit-1/rules.d/50-alc-poweroff.rules' in text
    assert 'rm -f /etc/polkit-1/localauthority/50-local.d/50-alc-poweroff.pkla' in text
    assert 'userdel "$LEGACY_USER"' in text


def test_uninstaller_cleans_legacy_alc_on_purge() -> None:
    text = UNINSTALLER.read_text(encoding="utf-8")
    assert 'LEGACY_USER="alc"' in text
    assert 'rm -f /etc/polkit-1/rules.d/50-alc-poweroff.rules' in text
    assert 'remove_user "$LEGACY_USER"' in text


@pytest.mark.skipif(shutil.which("rsync") is None, reason="rsync not installed")
def test_rsync_update_keeps_dest_device_config(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    (src / "backend").mkdir(parents=True)
    (src / "config.yaml").write_text(
        "device_model: alc8500_2_expert\nsimulator: true\nserial_port: ''\n",
        encoding="utf-8",
    )
    (src / "backend" / "app.txt").write_text("new", encoding="utf-8")
    dest.mkdir()
    dest_cfg = (
        "device_model: alc7000_expert\n"
        "serial_port: /dev/elv-alc\n"
        "simulator: false\n"
        "baudrate: 9600\n"
    )
    (dest / "config.yaml").write_text(dest_cfg, encoding="utf-8")

    subprocess.check_call(
        [
            "rsync",
            "-a",
            "--delete",
            "--exclude",
            "config.yaml",
            f"{src}/",
            f"{dest}/",
        ]
    )

    assert (dest / "config.yaml").read_text(encoding="utf-8") == dest_cfg
    assert (dest / "backend" / "app.txt").read_text(encoding="utf-8") == "new"
