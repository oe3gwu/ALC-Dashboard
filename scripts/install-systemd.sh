#!/usr/bin/env bash
# Installiert ELV ALC Dashboard nach /opt/alc und aktiviert Autostart via systemd.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${DEST:-/opt/alc}"
SERVICE_NAME="elv-alc-dashboard"
SERVICE_USER="${SERVICE_USER:-elv-alc}"
UNIT_SRC="$ROOT/systemd/elv-alc-dashboard.service"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"
UDEV_SRC="$ROOT/udev/99-elv-alc.rules"
UDEV_DST="/etc/udev/rules.d/99-elv-alc.rules"
POLKIT_RULES_SRC="$ROOT/polkit/50-elv-alc-poweroff.rules"
POLKIT_RULES_DST="/etc/polkit-1/rules.d/50-elv-alc-poweroff.rules"
POLKIT_PKLA_SRC="$ROOT/polkit/50-elv-alc-poweroff.pkla"
POLKIT_PKLA_DST="/etc/polkit-1/localauthority/50-local.d/50-elv-alc-poweroff.pkla"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Bitte mit sudo ausführen: sudo $0"
  exit 1
fi

echo "==> Zielverzeichnis: $DEST"
echo "==> Service-User:    $SERVICE_USER"

if ! id -u "$SERVICE_USER" &>/dev/null; then
  echo "==> Lege Systemuser $SERVICE_USER an…"
  useradd --system --home-dir "$DEST" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# dialout für Seriellzugriff
usermod -aG dialout "$SERVICE_USER" 2>/dev/null || true

echo "==> Synchronisiere Projektdateien nach $DEST…"
mkdir -p "$DEST"

# Gerätekonfig (Modell, Port, Simulator, Baud, …) bei Updates nicht auf Repo-Default zurücksetzen.
RSYNC_EXCLUDES=(
  --exclude '.git/'
  --exclude '.venv/'
  --exclude 'frontend/node_modules/'
  --exclude 'frontend/dist/'
  --exclude 'data/logger/*'
  --exclude 'data/battery-db.json'
  --exclude '__pycache__/'
  --exclude '*.pyc'
)
if [[ -f "$DEST/config.yaml" ]]; then
  echo "==> Bestehende Gerätekonfiguration bleibt erhalten ($DEST/config.yaml)"
  RSYNC_EXCLUDES+=(--exclude 'config.yaml')
fi
rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$ROOT/" "$DEST/"

mkdir -p "$DEST/data/logger"
# Bestehende Runtime-Daten nicht löschen
touch "$DEST/data/logger/.gitkeep"

echo "==> Python-venv + Dependencies…"
if [[ ! -x "$DEST/.venv/bin/python" ]]; then
  python3 -m venv "$DEST/.venv"
fi
"$DEST/.venv/bin/pip" install --upgrade pip
"$DEST/.venv/bin/pip" install -r "$DEST/backend/requirements.txt"

echo "==> Frontend bauen…"
INVOKER_HOME="${SUDO_USER:+$(getent passwd "$SUDO_USER" | cut -d: -f6)}"
INVOKER_HOME="${INVOKER_HOME:-$HOME}"
export PATH="${INVOKER_HOME}/.local/node/bin:/usr/local/bin:$PATH"
if ! command -v npm &>/dev/null; then
  echo "Fehler: npm nicht gefunden. Node.js 20+ installieren und erneut ausführen."
  exit 1
fi
(
  cd "$DEST/frontend"
  npm install
  npm run build
)

# Produktion: Service bindet 0.0.0.0 — config angleichen
if [[ -f "$DEST/config.yaml" ]]; then
  sed -i 's/^host:.*/host: "0.0.0.0"/' "$DEST/config.yaml" || true
fi

chown -R "$SERVICE_USER:dialout" "$DEST"
# venv muss für den Service-User ausführbar sein
chmod -R u+rX "$DEST"

echo "==> udev-Regel…"
# Remove legacy filename from older installs
rm -f /etc/udev/rules.d/99-elv-alc8500.rules
cp "$UDEV_SRC" "$UDEV_DST"
udevadm control --reload-rules
udevadm trigger || true

echo "==> Polkit (Herunterfahren in der UI)…"
mkdir -p /etc/polkit-1/rules.d /etc/polkit-1/localauthority/50-local.d
sed "s/__SERVICE_USER__/$SERVICE_USER/g" "$POLKIT_RULES_SRC" > "$POLKIT_RULES_DST"
sed "s/__SERVICE_USER__/$SERVICE_USER/g" "$POLKIT_PKLA_SRC" > "$POLKIT_PKLA_DST"
chmod 644 "$POLKIT_RULES_DST" "$POLKIT_PKLA_DST"
systemctl try-restart polkit.service 2>/dev/null || systemctl try-restart polkit 2>/dev/null || true

echo "==> systemd Unit…"
# Unit immer aus Repo-Vorlage, Pfade sind /opt/alc
cp "$UNIT_SRC" "$UNIT_DST"
# Falls DEST abweichend gesetzt wurde, Unit anpassen
if [[ "$DEST" != "/opt/alc" ]]; then
  sed -i "s|/opt/alc|$DEST|g" "$UNIT_DST"
fi
if [[ "$SERVICE_USER" != "elv-alc" ]]; then
  sed -i "s/^User=.*/User=$SERVICE_USER/" "$UNIT_DST"
fi

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo
echo "Fertig. Status:"
systemctl --no-pager --full status "$SERVICE_NAME" || true
echo
echo "UI:        http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080  oder  http://127.0.0.1:8080"
echo "Logs:      journalctl -u $SERVICE_NAME -f"
echo "Stoppen:   sudo systemctl stop $SERVICE_NAME"
echo "Autostart: sudo systemctl disable $SERVICE_NAME"
