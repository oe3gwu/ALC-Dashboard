# AI install prompt (Docker Compose)

Copy the block below into **Cursor**, **OpenCode**, or a similar coding agent. It runs the dashboard with Docker Compose (variant 2) from the repository checkout.

---

## Prompt (copy from here)

```
Install the ELV ALC Dashboard on this Linux machine using Docker Compose (variant 2 — container from the repo Dockerfile).

Goals:
- Build the local image and start the stack with docker compose
- UI reachable on port 8080 (simulator by default from config.yaml)
- Do not change application source code — installation / run only

Steps:
1. If the repo is not already present, clone https://github.com/oe3gwu/ELV-ALC-Dashboard.git and cd into it. If I already have a checkout, use that directory.
2. Verify prerequisites: Docker Engine and Docker Compose plugin (`docker compose version`). Prefer asking me to install Docker if missing rather than inventing workarounds.
3. From the repository root, run:
   docker compose up -d --build
4. Confirm success:
   - docker compose ps
   - Container elv-alc-dashboard is running
   - UI reachable at http://127.0.0.1:8080 (or http://<host-ip>:8080)

Notes for the agent:
- Compose mounts ./config.yaml and ./data into the container — do not delete my data/ or rewrite config unless I ask.
- Default config uses simulator: true; no USB device is required for a first successful start.
- For a real ALC later: I must set simulator: false and serial_port in config.yaml, and uncomment devices + group_add (dialout) in docker-compose.yml — only do that if I explicitly ask for hardware.
- Prefer docker compose (v2 plugin) over docker-compose (hyphen) if both exist.
- Report the final status and the URL to open.
```

---

## After install

```bash
docker compose ps
docker compose logs -f
```

Update later (rebuild image, keeps host `data/` + `config.yaml`):

```bash
cd ELV-ALC-Dashboard
git pull
docker compose up -d --build
```

Stop:

```bash
docker compose down
```
