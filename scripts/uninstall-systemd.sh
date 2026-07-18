#!/usr/bin/env bash
# Entfernt den systemd-Autostart. Dateien unter /opt/alc bleiben erhalten (außer --purge).
set -euo pipefail

DEST="${DEST:-/opt/alc}"
SERVICE_NAME="elv-alc-dashboard"
SERVICE_USER="${SERVICE_USER:-elv-alc}"
PURGE=false

for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=true ;;
    -h|--help)
      echo "Usage: sudo $0 [--purge]"
      echo "  --purge  zusätzlich /opt/alc und Systemuser $SERVICE_USER entfernen"
      exit 0
      ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Bitte mit sudo ausführen: sudo $0"
  exit 1
fi

echo "==> Stoppe und deaktiviere $SERVICE_NAME…"
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl reset-failed "$SERVICE_NAME" 2>/dev/null || true

if [[ "$PURGE" == true ]]; then
  echo "==> Entferne $DEST…"
  rm -rf "$DEST"
  if id -u "$SERVICE_USER" &>/dev/null; then
    echo "==> Entferne User $SERVICE_USER…"
    userdel "$SERVICE_USER" 2>/dev/null || true
  fi
  echo "==> udev-Regel belassen (harmlos). Zum Entfernen:"
  echo "    sudo rm -f /etc/udev/rules.d/99-elv-alc.rules /etc/udev/rules.d/99-elv-alc8500.rules && sudo udevadm control --reload-rules"
else
  echo "Hinweis: $DEST bleibt bestehen. Mit --purge komplett löschen."
fi

echo "Fertig."
