# AI install prompt (`/opt/alc` / systemd)

Copy the block below into **Cursor**, **OpenCode**, or a similar coding agent. It **always** fetches a fresh checkout of this repo, then runs a full systemd install/reinstall to `/opt/alc` (rebuild + restart).

For Docker Compose instead, see [ai-install-prompt-docker.md](ai-install-prompt-docker.md).

---

## Prompt (copy from here)

```
Install or reinstall the ELV ALC Dashboard on this Linux machine using the project's systemd installer (variant 1 → /opt/alc).

Goals:
- Fresh source from GitHub main (do not reuse a stale local tree)
- Full install to /opt/alc even if an older install already exists
- Rebuild frontend + Python deps, then enable/restart the systemd service
- Do not change application source code — install/reinstall only

Mandatory workflow (do not skip steps because something is "already installed"):
1. Source checkout (always refresh):
   - Preferred work dir: ~/Github/ELV-ALC-Dashboard or ~/ELV-ALC-Dashboard (create parent dirs if needed).
   - If the directory does not exist: git clone https://github.com/oe3gwu/ELV-ALC-Dashboard.git <dir>
   - If it already exists: cd into it, then force a clean main:
       git fetch origin
       git checkout main
       git reset --hard origin/main
       git clean -fd
     Do NOT keep local commits, dirty files, or an old branch as "good enough".
2. Prerequisites: Python 3.11+, Node.js/npm 20+, rsync, sudo/root. Fix missing tools, then continue.
3. From the repository root, ALWAYS run a full reinstall (even if /opt/alc or elv-alc-dashboard.service already exist):
   sudo ./scripts/install-systemd.sh
   The script must rsync to /opt/alc, recreate/update the venv, pip install, npm install + npm run build, install udev + unit, then enable --now / restart the service.
4. Confirm success:
   - sudo systemctl status elv-alc-dashboard  → active (running)
   - Service listens on 0.0.0.0:8080
   - UI reachable at http://<host-ip>:8080

Notes for the agent:
- "Already installed" is NOT a reason to stop. Always refresh git + rerun install-systemd.sh.
- Prefer asking me for the sudo password / confirmation rather than inventing workarounds.
- If npm/node is missing, install Node 20+ (or use ~/.local/node/bin if present) and retry the install script.
- Keep runtime data under /opt/alc/data when the installer preserves it; do not wipe battery DB / logger unless I ask.
- Report final service status and the URL to open.
```

---

## After install

```bash
sudo systemctl status elv-alc-dashboard
journalctl -u elv-alc-dashboard -f
```

Update later (same as reinstall — keeps `/opt/alc/data`):

```bash
cd ELV-ALC-Dashboard
git fetch origin && git checkout main && git reset --hard origin/main
sudo ./scripts/install-systemd.sh
```
