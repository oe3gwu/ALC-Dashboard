# AI install prompt (`/opt/alc` / systemd)

Copy the block below into **Cursor**, **OpenCode**, or a similar coding agent. It installs the dashboard with the systemd installer (variant 1) to `/opt/alc`.

For Docker Compose instead, see [ai-install-prompt-docker.md](ai-install-prompt-docker.md).

---

## Prompt (copy from here)

```
Install the ELV ALC Dashboard on this Linux machine using the project's systemd installer (variant 1 → /opt/alc).

Goals:
- Install to /opt/alc
- Enable and start the systemd service so the UI autostarts on boot
- Do not change application source code — installation only

Steps:
1. If the repo is not already present, clone https://github.com/oe3gwu/ELV-ALC-Dashboard.git and cd into it. If I already have a checkout, use that directory.
2. Verify prerequisites: Python 3.11+ with venv (`python3-venv` on Debian/Ubuntu), Node.js/npm 20+, rsync, and sudo/root.
   On Debian/Ubuntu if missing: `sudo apt install -y python3 python3-venv python3-pip rsync`
3. From the repository root, run:
   sudo ./scripts/install-systemd.sh
4. Confirm success:
   - sudo systemctl status elv-alc-dashboard
   - Service listens on 0.0.0.0:8080
   - UI reachable at http://<host-ip>:8080

Notes for the agent:
- The script creates system user elv-alc (dialout), rsyncs the project to /opt/alc, creates the venv, installs Python deps, builds the frontend, installs the udev rule and unit elv-alc-dashboard.service, then enable --now.
- Prefer asking me for sudo password / confirmation rather than inventing workarounds.
- If npm/node is missing, install Node 20+ (or use an existing user-local Node under ~/.local/node/bin if present) and retry the install script.
- Report the final status and the URL to open.
```

---

## After install

```bash
sudo systemctl status elv-alc-dashboard
journalctl -u elv-alc-dashboard -f
```

Update later (keeps `data/`):

```bash
cd ELV-ALC-Dashboard
git pull
sudo ./scripts/install-systemd.sh
```
