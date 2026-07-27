# AI install prompt (Docker Compose)

Copy the block below into **Cursor**, **OpenCode**, or a similar coding agent. It **always** fetches a fresh checkout, then rebuilds and (re)starts the Docker Compose stack.

For systemd (`/opt/alc`) instead, see [ai-install-prompt.md](ai-install-prompt.md).

---

## Prompt (copy from here)

```
Install or reinstall the ELV ALC Dashboard on this Linux machine using Docker Compose (variant 2 — container from the repo Dockerfile).

Goals:
- Fresh source from GitHub main (do not reuse a stale local tree)
- Full rebuild and recreate of the container even if it already runs
- UI on port 8080 (simulator by default from config.yaml)
- Do not change application source code — install/run only

Mandatory workflow (do not skip steps because something is "already running"):
1. Source checkout (always refresh):
   - Preferred work dir: ~/Github/ELV-ALC-Dashboard or ~/ELV-ALC-Dashboard (create parent dirs if needed).
   - If the directory does not exist: git clone https://github.com/oe3gwu/ELV-ALC-Dashboard.git <dir>
   - If it already exists: cd into it, then force a clean main:
       git fetch origin
       git checkout main
       git reset --hard origin/main
       git clean -fd
     Do NOT keep local commits, dirty files, or an old branch as "good enough".
2. Prerequisites: Docker Engine + Compose plugin (`docker compose version`). Prefer asking me to install Docker if missing.
3. From the repository root, ALWAYS rebuild and recreate (even if elv-alc-dashboard already exists):
   docker compose down
   docker compose up -d --build --force-recreate
4. Confirm success:
   - docker compose ps
   - Container elv-alc-dashboard is running
   - UI at http://127.0.0.1:8080 (or http://<host-ip>:8080)

Notes for the agent:
- "Already running" / "image exists" is NOT a reason to stop. Always refresh git + rebuild/recreate.
- Compose mounts ./config.yaml and ./data — do not delete my data/ or rewrite config unless I ask.
- Default config uses simulator: true; no USB device is required for a first successful start.
- For real ALC later: set simulator: false and serial_port in config.yaml, and uncomment devices + group_add (dialout) in docker-compose.yml — only if I explicitly ask for hardware.
- Prefer docker compose (v2 plugin) over docker-compose (hyphen).
- Report final status and the URL to open.
```

---

## After install

```bash
docker compose ps
docker compose logs -f
```

Update later (same as reinstall — keeps host `data/` + `config.yaml`):

```bash
cd ELV-ALC-Dashboard
git fetch origin && git checkout main && git reset --hard origin/main
docker compose down
docker compose up -d --build --force-recreate
```

Stop:

```bash
docker compose down
```
