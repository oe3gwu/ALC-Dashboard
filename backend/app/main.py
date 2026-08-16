from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.api.schemas import (
    ActivityRequest,
    BatteryDbIn,
    ChannelParamsIn,
    ConfigUpdate,
    ConnectRequest,
    DeviceGIn,
    DeviceHIn,
    DeviceJIn,
    StartProcessRequest,
    channel_from_in,
    diff_params,
)
from app.config import ROOT, load_config, save_config
from app.devices.profiles import get_profile, list_devices
from app.protocol.constants import (
    BATTERY_TYPES,
    PROGRAMS,
    SAMPLES_PER_BLOCK,
    program_incompatible_message,
)
from app.protocol.models import (
    DeviceParamsG,
    DeviceParamsH,
    DeviceParamsJ,
)
from app.serial_manager import SerialManager
from app.services.battery_db_archive import SLOT_COUNT, BatteryDbArchive, entry_to_model
from app.services.firmware_guide import build_firmware_guide
from app.services.live_series import LiveSeriesStore
from app.services.logger_archive import LoggerArchive
from app.services.pdf_export import build_logger_pdf, write_pdf

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("elv-alc")

cfg = load_config()
manager = SerialManager(cfg)
archive = LoggerArchive(cfg.data_path)
battery_db = BatteryDbArchive(cfg.data_path)
live_series = LiveSeriesStore()


def current_profile():
    return get_profile(cfg.device_model)


def channel_count() -> int:
    return current_profile().channel_count


def require_feature(name: str) -> None:
    feats = current_profile().features
    if not getattr(feats, name, False):
        raise HTTPException(400, f"Funktion „{name}“ für {current_profile().label} nicht verfügbar")


def valid_channel(channel: int) -> None:
    n = channel_count()
    if channel < 0 or channel >= n:
        raise HTTPException(400, f"Kanal 0–{n - 1}")


def ensure_program_compatible(params: Any) -> None:
    msg = program_incompatible_message(int(params.battery_type), int(params.program))
    if msg:
        raise HTTPException(400, msg)


def set_channel_params_http(client: Any, params: Any) -> Any:
    """set_channel_params with device NAK / ValueError → HTTP 400 (not 500)."""
    try:
        return client.set_channel_params(params)
    except ValueError as exc:
        text = str(exc)
        if "b'\\x04'" in text or text.rstrip().endswith("\\x04'"):
            raise HTTPException(
                400,
                "Gerät hat die Parameter abgelehnt. Prüfen Sie Programm und Akkutyp "
                "(Formieren/Zyklen/Auffrischen nur für NiCd/NiMH/NiZn).",
            ) from exc
        raise HTTPException(400, text) from exc


AUTO_CONNECT_RETRY_S = 5.0

_main_loop: asyncio.AbstractEventLoop | None = None
_autoconnect_task: asyncio.Task[None] | None = None
_sampler_task: asyncio.Task[None] | None = None
_SERIES_TICK_S = 1.0


class LiveBroadcaster:
    """Fan-out of the latest live payload to all /ws/live clients."""

    def __init__(self) -> None:
        self.last_payload: dict[str, Any] | None = None
        self._clients: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def discard(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def send_last(self, ws: WebSocket) -> None:
        if self.last_payload is not None:
            await ws.send_json(self.last_payload)

    async def publish(self, payload: dict[str, Any]) -> None:
        self.last_payload = payload
        dead: list[WebSocket] = []
        for client in list(self._clients):
            try:
                await client.send_json(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            self._clients.discard(client)


live_hub = LiveBroadcaster()


class DeviceLostError(Exception):
    """Link to the ALC died; mapped to HTTP 503 with a clear detail message."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def is_link_error(exc: BaseException) -> bool:
    """True for USB/serial transport failures (not WebSocket peer disconnect)."""
    import serial

    if isinstance(exc, (serial.SerialException, TimeoutError)):
        return True
    if isinstance(exc, OSError):
        errno = getattr(exc, "errno", None)
        if errno in {5, 6, 9, 19}:  # EIO, ENXIO, EBADF, ENODEV
            return True
        msg = str(exc).lower()
        if any(s in msg for s in ("device", "port is", "usb", "serial", "i/o error", "not open")):
            return True
    return False


async def _autoconnect_retry_loop() -> None:
    """Retry every 5s until connected or user disables via Disconnect.

    connect()/auto_detect runs in a worker thread so port probing cannot block
    the asyncio event loop (otherwise the UI sees NetworkError / hung fetches).
    """
    while manager.startup_autoconnect and not manager.is_connected:
        await asyncio.sleep(AUTO_CONNECT_RETRY_S)
        if not manager.startup_autoconnect or manager.is_connected:
            break
        try:
            await asyncio.to_thread(
                manager.connect,
                cfg.serial_port or None,
                cfg.simulator,
            )
            log.info("Auto-connect retry OK: %s", manager.status())
            break
        except Exception as exc:
            log.info("Auto-connect retry: %s", exc)


def ensure_autoconnect_task() -> None:
    """Start (or keep) the 5s reconnect loop if autoconnect is allowed and offline."""
    global _autoconnect_task
    if not manager.startup_autoconnect or manager.is_connected:
        return
    loop = _main_loop
    if loop is None or not loop.is_running():
        return

    def _start() -> None:
        global _autoconnect_task
        if not manager.startup_autoconnect or manager.is_connected:
            return
        if _autoconnect_task is not None and not _autoconnect_task.done():
            return
        _autoconnect_task = loop.create_task(_autoconnect_retry_loop())

    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        _start()
    else:
        loop.call_soon_threadsafe(_start)


def note_device_lost(exc: BaseException) -> DeviceLostError:
    """Mark link failed, schedule reconnect, return error for HTTP/WS surfaces."""
    manager.mark_failed(exc)
    ensure_autoconnect_task()
    return DeviceLostError(manager.last_error or "Geräteverbindung verloren")


async def _live_sampler_loop() -> None:
    """Poll the device on poll_interval; append 1 Hz samples even with 0 browsers."""
    loop = asyncio.get_running_loop()
    next_poll = 0.0
    next_series = 0.0
    while True:
        try:
            now = loop.time()
            poll_every = max(0.2, float(cfg.poll_interval) or 1.5)
            wait = min(next_poll, next_series) - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = loop.time()

            if now >= next_poll:
                try:
                    payload = await asyncio.to_thread(_live_payload_nonblocking)
                except Exception as exc:
                    if is_link_error(exc):
                        note_device_lost(exc)
                        payload = {
                            "type": "live",
                            "connection": manager.status(),
                            "channels": [],
                            "measurements": [],
                            "temperatures": {},
                        }
                    else:
                        log.debug("live sampler poll: %s", exc)
                        payload = None
                if payload is not None:
                    await live_hub.publish(payload)
                next_poll = loop.time() + poll_every

            now = loop.time()
            if now >= next_series:
                snap = live_hub.last_payload
                if snap is not None and snap.get("type") != "error":
                    live_series.ingest(snap.get("channels") or [], snap.get("measurements") or [])
                next_series = loop.time() + _SERIES_TICK_S
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("live sampler")
            await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _main_loop, _autoconnect_task, _sampler_task
    cfg.data_path.mkdir(parents=True, exist_ok=True)
    (cfg.data_path / "logger").mkdir(parents=True, exist_ok=True)
    _main_loop = asyncio.get_running_loop()
    # Hardware: leerer serial_port → auto_detect; Simulator: immer verbinden
    try:
        manager.connect(port=cfg.serial_port or None, use_simulator=cfg.simulator)
        log.info("Auto-connect: %s", manager.status())
    except Exception as exc:
        log.warning("Auto-connect fehlgeschlagen: %s", exc)

    ensure_autoconnect_task()
    _sampler_task = asyncio.create_task(_live_sampler_loop())

    yield

    sampler = _sampler_task
    _sampler_task = None
    if sampler is not None:
        sampler.cancel()
        try:
            await sampler
        except asyncio.CancelledError:
            pass
    task = _autoconnect_task
    _autoconnect_task = None
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _main_loop = None
    manager.disconnect()


app = FastAPI(title="ELV ALC Dashboard", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DeviceLostError)
async def device_lost_handler(_request: Request, exc: DeviceLostError) -> Response:
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=503, content={"detail": exc.message})


@app.exception_handler(TimeoutError)
async def timeout_link_handler(_request: Request, exc: TimeoutError) -> Response:
    from fastapi.responses import JSONResponse

    err = note_device_lost(exc)
    return JSONResponse(status_code=503, content={"detail": err.message})


def _register_serial_exception_handler() -> None:
    import serial

    @app.exception_handler(serial.SerialException)
    async def serial_link_handler(_request: Request, exc: serial.SerialException) -> Response:
        from fastapi.responses import JSONResponse

        err = note_device_lost(exc)
        return JSONResponse(status_code=503, content={"detail": err.message})


_register_serial_exception_handler()


def require_client():
    if not manager.is_connected:
        raise HTTPException(400, "Nicht mit dem ALC verbunden")
    return manager.client


# ——— Meta / connection ———


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    profile = current_profile()
    allowed_bt = {k: v for k, v in BATTERY_TYPES.items() if k in profile.battery_type_ids or k == 0xFF}
    allowed_prog = {k: v for k, v in PROGRAMS.items() if k in profile.program_ids}
    caps = {
        "channel_count": profile.channel_count,
        "battery_type_ids": list(profile.battery_type_ids),
        "program_ids": list(profile.program_ids),
        "logger": profile.features.logger,
        "battery_db": profile.features.battery_db,
        "chemistry_params": profile.features.chemistry_params,
        "chemistry_hj": profile.features.chemistry_hj,
        "full_factor": profile.features.full_factor,
        "activator": profile.features.activator,
        "activator_channel": profile.features.activator_channel,
        "ri_usb": profile.features.ri_usb,
        "firmware_guided": profile.features.firmware_guided,
        "protocol": profile.protocol,
        "simulator_label": profile.simulator_label,
    }
    return {
        "name": "ELV ALC Dashboard",
        "version": "1.0.0",
        "device_model": profile.id,
        "devices": list_devices(),
        "battery_types": allowed_bt,
        "programs": allowed_prog,
        "battery_types_all": BATTERY_TYPES,
        "programs_all": PROGRAMS,
        "capabilities": caps,
        "config": {
            "serial_port": cfg.serial_port,
            "device_model": cfg.device_model,
            "simulator": cfg.simulator,
            "mock": cfg.simulator,
            "poll_interval": cfg.poll_interval,
            "host": cfg.host,
            "port": cfg.port,
        },
        "features": {
            "ri_measurement": False,
            "ri_note": "Innenwiderstandsmessung nur am Gerät (kein USB-Befehl).",
            "firmware_update": "guided" if profile.features.firmware_guided else "none",
            **caps,
        },
    }


@app.get("/api/ports")
def ports() -> dict[str, Any]:
    from app.serial_manager import dialout_status

    return {
        "ports": [p.to_dict() for p in manager.list_ports()],
        "dialout": dialout_status(),
    }


@app.get("/api/connection")
def connection() -> dict[str, Any]:
    return manager.status()


@app.post("/api/connection/connect")
def connect(body: ConnectRequest) -> dict[str, Any]:
    try:
        sim = body.simulator if body.simulator is not None else body.mock
        return manager.connect(port=body.port, use_simulator=sim, use_mock=body.mock)
    except Exception as exc:
        manager.last_error = str(exc)
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/connection/disconnect")
def disconnect() -> dict[str, Any]:
    # Stop auto-retry; intentional disconnect must stay disconnected
    manager.startup_autoconnect = False
    manager.disconnect()
    manager.last_error = None
    return manager.status()


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return cfg.dump_for_yaml() | {"mock": cfg.simulator}


@app.put("/api/config")
def update_config(body: ConfigUpdate) -> dict[str, Any]:
    global cfg
    old_model = cfg.device_model
    old_sim = cfg.simulator
    old_port = (cfg.serial_port or "").strip()
    data = cfg.dump_for_yaml()
    updates = body.model_dump(exclude_none=True)
    if "mock" in updates and "simulator" not in updates:
        updates["simulator"] = bool(updates.pop("mock"))
    else:
        updates.pop("mock", None)
    if "device_model" in updates:
        prof = get_profile(updates["device_model"])
        if not prof.enabled:
            raise HTTPException(400, f"Gerät {prof.label} ist nicht wählbar ({prof.disabled_reason})")
    # Simulator nur ohne Port
    serial = updates.get("serial_port", data.get("serial_port", ""))
    if serial and str(serial).strip():
        updates["simulator"] = False
    data.update(updates)
    data.pop("mock", None)
    cfg = type(cfg).model_validate(data)
    save_config(cfg)
    manager.cfg = cfg

    new_port = (cfg.serial_port or "").strip()
    conn_changed = (
        cfg.device_model != old_model
        or cfg.simulator != old_sim
        or new_port != old_port
    )
    reconnect_status: dict[str, Any] | None = None
    if conn_changed:
        try:
            if cfg.simulator:
                reconnect_status = manager.connect(port="", use_simulator=True)
            elif new_port:
                reconnect_status = manager.connect(port=new_port, use_simulator=False)
            else:
                # Leerer Port + kein Simulator → auto_detect (nicht nur disconnect)
                reconnect_status = manager.connect(port="", use_simulator=False)
        except Exception as exc:
            log.warning("Reconnect nach Config-Änderung fehlgeschlagen: %s", exc)
            manager.last_error = str(exc)
            reconnect_status = manager.status()

    out = cfg.dump_for_yaml() | {"mock": cfg.simulator}
    if reconnect_status is not None:
        out["connection"] = reconnect_status
    return out


# ——— Live / channels ———


def _channel_live_dict(client: Any, channel: int) -> dict[str, Any]:
    """Params from ``p``, but live stage from ``a`` (FW keeps ``p`` stage at idle during faults)."""
    d = client.get_channel_params(channel).to_dict()
    # Never trust a possibly wrong echoed channel byte from the device.
    d["channel"] = channel
    try:
        act = client.get_activity(channel)
        d["stage"] = act.stage
        d["stage_name"] = act.stage_name
        d["idle"] = act.stage_name == "Leerlauf"
    except Exception as exc:
        log.debug("activity ch%s: %s", channel, exc)
    return d


@app.get("/api/live")
def live() -> dict[str, Any]:
    client = require_client()
    n = channel_count()
    try:
        with manager.with_client():
            # Measurements before params: some FW NAKs bare ``m`` after reading unused channels
            measurements = [m.to_dict() for m in client.get_measurements()[:n]]
            temps = client.get_temperatures().to_dict()
            channels = [_channel_live_dict(client, i) for i in range(n)]
    except Exception as exc:
        if is_link_error(exc):
            raise note_device_lost(exc) from exc
        manager.last_error = str(exc)
        raise HTTPException(503, f"Live-Abfrage fehlgeschlagen: {exc}") from exc
    return {"channels": channels, "measurements": measurements, "temperatures": temps, "connection": manager.status()}


@app.get("/api/live/series")
def live_series_get() -> dict[str, Any]:
    """Full in-process U/I/C history (up to 6 h). Independent of client host/origin."""
    return live_series.snapshot()


@app.get("/api/channels/{channel}")
def get_channel(channel: int) -> dict[str, Any]:
    valid_channel(channel)
    client = require_client()
    with manager.with_client():
        return client.get_channel_params(channel).to_dict()


@app.put("/api/channels/{channel}")
def set_channel(channel: int, body: ChannelParamsIn) -> dict[str, Any]:
    if channel != body.channel:
        body.channel = channel
    client = require_client()
    params = channel_from_in(body)
    ensure_program_compatible(params)
    with manager.with_client():
        echoed = set_channel_params_http(client, params)
    req = params.to_dict()
    echo = echoed.to_dict()
    return {"params": echo, "corrections": diff_params(req, echo)}


@app.post("/api/channels/{channel}/activity")
def activity(channel: int, body: ActivityRequest) -> dict[str, Any]:
    body.channel = channel
    client = require_client()
    with manager.with_client():
        state = client.set_activity(channel, stop=body.stop)
    return state.to_dict()


@app.post("/api/process/preview")
def process_preview(body: StartProcessRequest) -> dict[str, Any]:
    """Set params without starting; return corrections (CP security dialog)."""
    client = require_client()
    params = channel_from_in(body.params)
    valid_channel(params.channel)
    ensure_program_compatible(params)
    prof = current_profile()
    if getattr(params, "activator", False) and (
        not prof.features.activator or params.channel != prof.features.activator_channel
    ):
        raise HTTPException(400, "Aktivator für diesen Kanal/dieses Gerät nicht verfügbar")
    with manager.with_client():
        current = client.get_channel_params(params.channel)
        if current.stage_name != "Leerlauf":
            raise HTTPException(400, "Kanal ist nicht im Leerlauf")
        echoed = set_channel_params_http(client, params)
    req = params.to_dict()
    echo = echoed.to_dict()
    return {
        "requested": req,
        "device": echo,
        "corrections": diff_params(req, echo),
        "ready": True,
    }


@app.post("/api/process/start")
def process_start(body: StartProcessRequest) -> dict[str, Any]:
    if not body.confirm:
        raise HTTPException(400, "Bestätigung erforderlich (confirm=true)")
    client = require_client()
    params = channel_from_in(body.params)
    valid_channel(params.channel)
    ensure_program_compatible(params)
    prof = current_profile()
    if getattr(params, "activator", False) and (
        not prof.features.activator or params.channel != prof.features.activator_channel
    ):
        raise HTTPException(400, "Aktivator für diesen Kanal/dieses Gerät nicht verfügbar")
    with manager.with_client():
        echoed = set_channel_params_http(client, params)
        live_series.clear(params.channel)
        state = client.set_activity(params.channel, stop=False)
    return {
        "params": echoed.to_dict(),
        "activity": state.to_dict(),
        "corrections": diff_params(params.to_dict(), echoed.to_dict()),
    }


# ——— Battery database (local presets + ALC sync) ———


@app.get("/api/battery-db")
def list_battery_db() -> dict[str, Any]:
    require_feature("battery_db")
    return {"entries": battery_db.load(), "source": "local"}


def _battery_db_progress_stream(
    worker_fn: Any,
) -> StreamingResponse:
    """NDJSON progress stream helper (same pattern as logger readout)."""
    loop = asyncio.get_running_loop()
    events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def emit(item: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(events.put_nowait, item)

    def worker() -> None:
        try:
            worker_fn(emit)
        except Exception as exc:
            manager.last_error = str(exc)
            emit({"type": "error", "message": str(exc)})

    async def event_stream() -> AsyncIterator[str]:
        task = asyncio.create_task(asyncio.to_thread(worker))
        try:
            while True:
                item = await events.get()
                yield json.dumps(item, ensure_ascii=False) + "\n"
                if item.get("type") in ("done", "error"):
                    break
        finally:
            await task

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/battery-db/import-from-device")
def import_battery_db_from_device() -> dict[str, Any]:
    require_feature("battery_db")
    client = require_client()
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with manager.with_client():
        for slot in range(SLOT_COUNT):
            try:
                entries.append(client.get_battery_db(slot).to_dict())
            except Exception as exc:
                errors.append({"slot": slot, "error": str(exc)})
                entries.append({"slot": slot, "name": ""})
    saved = battery_db.replace_all(entries)
    return {
        "entries": saved,
        "imported": SLOT_COUNT - len(errors),
        "total": SLOT_COUNT,
        "errors": errors,
    }


@app.post("/api/battery-db/import-from-device/stream")
async def import_battery_db_from_device_stream() -> StreamingResponse:
    require_feature("battery_db")
    client = require_client()

    def run(emit: Any) -> None:
        entries: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        emit({"type": "progress", "done": 0, "total": SLOT_COUNT, "slot": 0, "pct": 0})
        with manager.with_client():
            for slot in range(SLOT_COUNT):
                try:
                    entries.append(client.get_battery_db(slot).to_dict())
                except Exception as exc:
                    errors.append({"slot": slot, "error": str(exc)})
                    entries.append({"slot": slot, "name": ""})
                done = slot + 1
                emit(
                    {
                        "type": "progress",
                        "done": done,
                        "total": SLOT_COUNT,
                        "slot": slot,
                        "pct": int(round(100.0 * done / SLOT_COUNT)),
                    }
                )
        saved = battery_db.replace_all(entries)
        emit(
            {
                "type": "done",
                "entries": saved,
                "imported": SLOT_COUNT - len(errors),
                "total": SLOT_COUNT,
                "errors": errors,
            }
        )

    return _battery_db_progress_stream(run)


@app.post("/api/battery-db/export-to-device")
def export_battery_db_to_device() -> dict[str, Any]:
    require_feature("battery_db")
    client = require_client()
    local = battery_db.load()
    written = 0
    errors: list[dict[str, Any]] = []
    with manager.with_client():
        for slot in range(SLOT_COUNT):
            try:
                entry = entry_to_model(local[slot])
                client.set_battery_db(entry)
                written += 1
            except Exception as exc:
                errors.append({"slot": slot, "error": str(exc)})
    if written == 0 and errors:
        raise HTTPException(500, f"Export fehlgeschlagen: {errors[0]['error']}")
    return {"written": written, "total": SLOT_COUNT, "errors": errors}


@app.post("/api/battery-db/export-to-device/stream")
async def export_battery_db_to_device_stream() -> StreamingResponse:
    require_feature("battery_db")
    client = require_client()
    local = battery_db.load()

    def run(emit: Any) -> None:
        written = 0
        errors: list[dict[str, Any]] = []
        emit({"type": "progress", "done": 0, "total": SLOT_COUNT, "slot": 0, "pct": 0})
        with manager.with_client():
            for slot in range(SLOT_COUNT):
                try:
                    entry = entry_to_model(local[slot])
                    client.set_battery_db(entry)
                    written += 1
                except Exception as exc:
                    errors.append({"slot": slot, "error": str(exc)})
                done = slot + 1
                emit(
                    {
                        "type": "progress",
                        "done": done,
                        "total": SLOT_COUNT,
                        "slot": slot,
                        "pct": int(round(100.0 * done / SLOT_COUNT)),
                    }
                )
        if written == 0 and errors:
            emit({"type": "error", "message": f"Export fehlgeschlagen: {errors[0]['error']}"})
            return
        emit({"type": "done", "written": written, "total": SLOT_COUNT, "errors": errors})

    return _battery_db_progress_stream(run)


@app.get("/api/battery-db/file")
def download_battery_db_file() -> Response:
    data = battery_db.to_json_bytes()
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="battery-db.json"'},
    )


@app.post("/api/battery-db/file")
async def upload_battery_db_file(
    request: Request,
    file: UploadFile | None = File(None),
) -> dict[str, Any]:
    payload: Any
    if file is not None and file.filename:
        raw = await file.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(400, f"Ungültige JSON-Datei: {exc}") from exc
    else:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(400, f"JSON-Datei oder Body erwartet: {exc}") from exc

    raw_entries = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(raw_entries, list):
        raise HTTPException(400, "Erwartet { entries: [...] }")
    try:
        saved = battery_db.replace_all(raw_entries)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"entries": saved, "source": "file"}


@app.get("/api/battery-db/{slot}")
def get_battery_db(slot: int) -> dict[str, Any]:
    if slot < 0 or slot >= SLOT_COUNT:
        raise HTTPException(400, "Slot 0–39")
    return battery_db.get(slot)


@app.put("/api/battery-db/{slot}")
def put_battery_db(slot: int, body: BatteryDbIn) -> dict[str, Any]:
    if slot < 0 or slot >= SLOT_COUNT:
        raise HTTPException(400, "Slot 0–39")
    body.slot = slot
    return battery_db.put(slot, body.model_dump())


@app.delete("/api/battery-db/{slot}")
def reset_battery_db(slot: int) -> dict[str, Any]:
    """Reset one local preset to defaults — does not write to the device."""
    require_feature("battery_db")
    if slot < 0 or slot >= SLOT_COUNT:
        raise HTTPException(400, "Slot 0–39")
    return battery_db.reset(slot)


# ——— Chemistry / device params ———


@app.get("/api/device/params")
def get_device_params() -> dict[str, Any]:
    require_feature("chemistry_params")
    client = require_client()
    with manager.with_client():
        g = client.get_device_g().to_dict()
        h = client.get_device_h().to_dict()
        j = client.get_device_j().to_dict()
    return {"g": g, "h": h, "j": j}


@app.put("/api/device/params/g")
def put_g(body: DeviceGIn) -> dict[str, Any]:
    require_feature("chemistry_params")
    client = require_client()
    with manager.with_client():
        return client.set_device_g(DeviceParamsG(**body.model_dump())).to_dict()


@app.put("/api/device/params/h")
def put_h(body: DeviceHIn) -> dict[str, Any]:
    require_feature("chemistry_params")
    client = require_client()
    with manager.with_client():
        cur = client.get_device_h()
        for k, v in body.model_dump().items():
            setattr(cur, k, v)
        return client.set_device_h(cur).to_dict()


@app.put("/api/device/params/j")
def put_j(body: DeviceJIn) -> dict[str, Any]:
    require_feature("chemistry_params")
    client = require_client()
    # Illum 0x07 + ALBEEP 0x08 + BUBEEP 0x10 — keep any other bits from device
    illum_beep_mask = 0x07 | 0x08 | 0x10
    flags = body.illumination & 0x07
    if body.alarm_beep:
        flags |= 0x08
    if body.button_beep:
        flags |= 0x10
    with manager.with_client():
        cur = client.get_device_j()
        params = DeviceParamsJ(
            discharge_LiFePO4_mV=body.discharge_LiFePO4_mV,
            placeholder=cur.placeholder,
            charge_LiFePO4_mV=body.charge_LiFePO4_mV,
            maintain_LiFePO4_mV=body.maintain_LiFePO4_mV,
            placeholder2=cur.placeholder2,
            setup_flags=(cur.setup_flags & ~illum_beep_mask) | flags,
            contrast=body.contrast,
        )
        return client.set_device_j(params).to_dict()


@app.post("/api/device/params/restore")
def restore_defaults() -> dict[str, Any]:
    require_feature("chemistry_params")
    client = require_client()
    with manager.with_client():
        g = client.set_device_g(DeviceParamsG())
        h = client.set_device_h(DeviceParamsH())
        j = client.set_device_j(DeviceParamsJ())
    return {"g": g.to_dict(), "h": h.to_dict(), "j": j.to_dict()}


@app.get("/api/device/info")
def device_info() -> dict[str, Any]:
    client = require_client()
    st = manager.status()
    profile = get_profile(st.get("device_model") or cfg.device_model)
    try:
        with manager.with_client():
            temps = client.get_temperatures().to_dict()
    except Exception as exc:
        if is_link_error(exc):
            raise note_device_lost(exc) from exc
        raise
    info: dict[str, Any] = {
        "connected": True,
        "port": manager.connected_port,
        "simulator": manager.simulator,
        "mock": manager.simulator,
        "device_model": profile.id,
        "device_label": profile.label,
        "status_label": st.get("status_label"),
        "temperatures": temps,
        "channel_count": profile.channel_count,
    }
    if profile.features.chemistry_params:
        try:
            with manager.with_client():
                j = client.get_device_j()
            info["contrast"] = j.contrast
            info["illumination"] = j.illumination
        except Exception:
            pass
    if manager.simulator and hasattr(manager._transport, "serial_number"):
        info["serial_number"] = manager._transport.serial_number  # type: ignore[union-attr]
        info["firmware"] = getattr(manager._transport, "firmware", None)  # type: ignore[union-attr]
    elif profile.protocol == "alc7000_rs232" and not manager.simulator:
        try:
            with manager.with_client():
                ident = getattr(client, "identify", None)
                if callable(ident):
                    info["identity"] = ident()
        except Exception:
            info["serial_number"] = None
            info["firmware"] = None
    else:
        # ALC 8500-2 / 5000-family: Ident ``u`` → FW-Feld + Seriennummer
        try:
            with manager.with_client():
                read_u = getattr(client, "read_ident_u", None)
                if callable(read_u):
                    fw, sn = read_u()
                    info["firmware"] = fw
                    info["serial_number"] = sn
                    info["ident_prefix"] = fw[:1] if fw else None
                else:
                    info["serial_number"] = None
                    info["firmware"] = None
                    info["note"] = (
                        "Seriennummer/FW werden vom Gerät nicht über das Standardprotokoll geliefert."
                    )
        except Exception:
            info["serial_number"] = None
            info["firmware"] = None
            info["note"] = "Ident u konnte nicht gelesen werden."
    return info


# ——— Logger ———


@app.get("/api/logger/{channel}")
def read_logger(channel: int, save: bool = True) -> dict[str, Any]:
    require_feature("logger")
    valid_channel(channel)
    client = require_client()
    try:
        with manager.with_client():
            data = client.read_logger(channel)
    except Exception as exc:
        if is_link_error(exc):
            raise note_device_lost(exc) from exc
        manager.last_error = str(exc)
        raise HTTPException(503, f"Logger-Lesen fehlgeschlagen: {exc}") from exc
    result: dict[str, Any] = {"logger": data.to_dict()}
    if save:
        meta = archive.save(data)
        result["archive"] = meta
        pdf_path = cfg.data_path / "logger" / f"{meta['id']}.pdf"
        write_pdf(data.to_dict() | {"saved_at": meta["saved_at"]}, pdf_path)
        result["archive"]["pdf"] = pdf_path.name
    return result


@app.get("/api/logger/{channel}/stream")
async def read_logger_stream(channel: int, save: bool = True) -> StreamingResponse:
    """NDJSON stream: progress lines, then done (or error).

    Progress is pushed via asyncio so the live WebSocket cannot stall the ASGI
    event loop while the serial lock is held for the multi-block readout.
    """
    require_feature("logger")
    valid_channel(channel)
    client = require_client()
    loop = asyncio.get_running_loop()
    events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def emit(item: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(events.put_nowait, item)

    def on_progress(block: int, total: int, expected: int) -> None:
        samples = min(block * SAMPLES_PER_BLOCK, expected) if expected else block * SAMPLES_PER_BLOCK
        pct = int(round(100.0 * block / total)) if total else 100
        emit(
            {
                "type": "progress",
                "block": block,
                "total": total,
                "samples": samples,
                "expected": expected,
                "pct": min(100, max(0, pct)),
            }
        )

    def worker() -> None:
        try:
            with manager.with_client():
                data = client.read_logger(channel, on_progress=on_progress)
            result: dict[str, Any] = {"type": "done", "logger": data.to_dict()}
            if save:
                meta = archive.save(data)
                result["archive"] = meta
                pdf_path = cfg.data_path / "logger" / f"{meta['id']}.pdf"
                write_pdf(data.to_dict() | {"saved_at": meta["saved_at"]}, pdf_path)
                result["archive"]["pdf"] = pdf_path.name
            emit(result)
        except Exception as exc:
            if is_link_error(exc):
                err = note_device_lost(exc)
                emit({"type": "error", "message": err.message})
            else:
                manager.last_error = str(exc)
                emit({"type": "error", "message": f"Logger-Lesen fehlgeschlagen: {exc}"})

    async def event_stream() -> AsyncIterator[str]:
        task = asyncio.create_task(asyncio.to_thread(worker))
        try:
            while True:
                item = await events.get()
                yield json.dumps(item, ensure_ascii=False) + "\n"
                if item.get("type") in ("done", "error"):
                    break
        finally:
            await task

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.delete("/api/logger/{channel}")
def clear_logger(channel: int) -> dict[str, Any]:
    require_feature("logger")
    valid_channel(channel)
    client = require_client()
    with manager.with_client():
        client.clear_logger(channel)
    return {"ok": True, "channel": channel}


@app.get("/api/archive")
def list_archive() -> dict[str, Any]:
    return {"sessions": archive.list_sessions()}


@app.delete("/api/archive")
def delete_all_archive() -> dict[str, Any]:
    deleted = archive.delete_all()
    return {"ok": True, "deleted": deleted}


@app.get("/api/archive/{session_id}")
def get_archive(session_id: str) -> dict[str, Any]:
    try:
        return archive.load(session_id)
    except ValueError as exc:
        raise HTTPException(400, "Ungültige Session-ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Session nicht gefunden") from exc


@app.delete("/api/archive/{session_id}")
def delete_archive(session_id: str) -> dict[str, Any]:
    try:
        archive.delete(session_id)
    except ValueError as exc:
        raise HTTPException(400, "Ungültige Session-ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Session nicht gefunden") from exc
    return {"ok": True, "id": session_id}


@app.get("/api/archive/{session_id}/export/{fmt}")
def export_archive(session_id: str, fmt: str):
    try:
        if fmt == "pdf":
            session = archive.load(session_id)
            pdf = build_logger_pdf(session)
            return Response(
                pdf,
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{session_id}.pdf"'},
            )
        path = archive.path_for(session_id, fmt)
        media = "application/json" if fmt == "json" else "text/csv"
        return FileResponse(path, media_type=media, filename=path.name)
    except ValueError as exc:
        raise HTTPException(400, "Ungültige Session-ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Export nicht gefunden") from exc


# ——— Firmware guide ———


@app.get("/api/firmware/guide")
def firmware_guide() -> dict[str, Any]:
    """Read-only guided instructions — never flashes firmware from this app."""
    return build_firmware_guide(current_profile().id)


# ——— WebSocket live ———


def _ws_disconnected(exc: BaseException) -> bool:
    """True when the WebSocket peer is gone — stop the live loop (do not retry send).

    Do not treat serial/OSError link failures as peer disconnect; those are handled
    in _live_payload_nonblocking via mark_failed + status push.
    """
    if isinstance(exc, WebSocketDisconnect):
        return True
    if isinstance(exc, (ConnectionError, asyncio.CancelledError)):
        return True
    # Starlette / uvicorn may wrap transport errors
    name = type(exc).__name__
    return name in {"ClientDisconnected", "WebSocketException", "ConnectionClosedError", "ConnectionClosedOK"}


def _live_payload_nonblocking() -> dict[str, Any] | None:
    """Build a live snapshot without blocking the asyncio loop.

    Returns None when the serial lock is held (e.g. logger readout) so the
    WebSocket can skip a tick instead of freezing ASGI streaming responses.
    """
    if not manager.is_connected:
        return {
            "type": "live",
            "connection": manager.status(),
            "channels": [],
            "measurements": [],
            "temperatures": {},
        }
    if not manager.try_acquire():
        return None
    try:
        client = manager.client
        n = channel_count()
        measurements = [m.to_dict() for m in client.get_measurements()[:n]]
        temps = client.get_temperatures().to_dict()
        channels = [_channel_live_dict(client, i) for i in range(n)]
        return {
            "type": "live",
            "channels": channels,
            "measurements": measurements,
            "temperatures": temps,
            "connection": manager.status(),
        }
    except Exception as exc:
        if is_link_error(exc):
            note_device_lost(exc)
            return {
                "type": "live",
                "connection": manager.status(),
                "channels": [],
                "measurements": [],
                "temperatures": {},
            }
        raise
    finally:
        manager.release()


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await ws.accept()
    live_hub.add(ws)
    try:
        try:
            await live_hub.send_last(ws)
        except Exception:
            return
        while True:
            msg = await ws.receive()
            if msg.get("type") in {"websocket.disconnect", "websocket.close"}:
                return
    except WebSocketDisconnect:
        return
    except Exception as exc:
        if not _ws_disconnected(exc):
            log.debug("ws/live ended: %s", exc)
        return
    finally:
        live_hub.discard(ws)
        try:
            await ws.close()
        except Exception:
            pass


# ——— Static frontend (SPA: F5 on /start etc. must serve index.html) ———

FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    _assets = FRONTEND_DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        """Serve built files, otherwise index.html for client-side routes."""
        headers_no_cache = {"Cache-Control": "no-cache, no-store, must-revalidate"}
        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            try:
                candidate.relative_to(FRONTEND_DIST.resolve())
            except ValueError:
                return FileResponse(FRONTEND_DIST / "index.html", headers=headers_no_cache)
            if candidate.is_file():
                # Hashed /assets/* can be cached; HTML + SW must always revalidate.
                name = candidate.name
                if name in ("index.html", "sw.js", "manifest.webmanifest") or full_path.endswith(
                    (".html", "sw.js", "manifest.webmanifest")
                ):
                    return FileResponse(candidate, headers=headers_no_cache)
                return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html", headers=headers_no_cache)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=cfg.host,
        port=cfg.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
