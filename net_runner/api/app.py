"""FastAPI application — REST + WebSocket for the net-runner simulator."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from net_runner.api_sim import api_call
from net_runner.catalog import DEVICE_SKUS, FAILURE_MODES, DeviceState
from net_runner.models import (
    AlertOut,
    ChaosInjectRequest,
    ChaosPatternRequest,
    DeviceOut,
    RemedyActionResult,
    SimControlRequest,
    SiteOut,
    TopologyEdge,
    TopologyNode,
    TopologyOut,
    WorldSummaryOut,
)
from net_runner.sim import SimulationEngine, generate_world

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global simulation state
# ---------------------------------------------------------------------------

_engine: Optional[SimulationEngine] = None
_ws_clients: set[WebSocket] = set()


async def _broadcast(data: dict[str, Any]) -> None:
    """Send JSON to all connected WebSocket clients."""
    if not _ws_clients:
        return
    msg = json.dumps(data, default=str)
    dead: set[WebSocket] = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _ws_clients -= dead


def _on_sim_event(event: Any) -> None:
    """Broadcast simulation events to all connected WebSocket clients."""
    from net_runner.models import SimEvent
    e: SimEvent = event
    payload = {
        "type": "alert",
        "data": {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "sim_time": e.sim_time.isoformat(),
            "event_type": e.event_type,
            "device_id": e.device_id,
            "hostname": e.hostname,
            "vendor": e.vendor,
            "site_name": e.site_name,
            "failure_mode_id": e.failure_mode_id,
            "severity": e.severity,
            "message": e.message,
            "is_manual": e.is_manual,
            "cascade_from_device_id": e.cascade_from_device_id,
            "previous_state": e.previous_state,
            "new_state": e.new_state,
        },
    }
    asyncio.create_task(_broadcast(payload))

    # Also send device update if state changed
    if e.device_id and _engine:
        device = _engine.world.devices.get(e.device_id)
        if device:
            asyncio.create_task(_broadcast({
                "type": "device_update",
                "data": DeviceOut.from_instance(device).model_dump(mode="json"),
            }))


async def _tick_broadcaster() -> None:
    """Periodically push world summary and tick signal to all clients."""
    while True:
        await asyncio.sleep(2.0)
        if _engine and _ws_clients:
            summary = _build_summary()
            await _broadcast({"type": "tick", "data": summary.model_dump(mode="json")})


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine
    world = generate_world(seed=42)
    _engine = SimulationEngine(world)
    _engine.on_event(_on_sim_event)
    await _engine.start()
    asyncio.create_task(_tick_broadcaster())
    logger.info("net-runner simulation started — seed=42, %d devices", len(world.devices))
    yield
    await _engine.stop()


app = FastAPI(
    title="net-runner",
    description="IT infrastructure simulation API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_engine() -> SimulationEngine:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Simulation not initialized")
    return _engine


def _build_summary() -> WorldSummaryOut:
    e = _get_engine()
    w = e.world
    states = [d.state for d in w.devices.values()]
    return WorldSummaryOut(
        id=w.id,
        seed=w.seed,
        org_name=w.org_name,
        sim_time=w.clock.sim_now,
        sim_speed=w.clock.speed_multiplier,
        is_running=w.clock.is_running,
        total_devices=len(w.devices),
        healthy_count=sum(1 for s in states if s == DeviceState.HEALTHY),
        degraded_count=sum(1 for s in states if s == DeviceState.DEGRADED),
        failed_count=sum(1 for s in states if s == DeviceState.FAILED),
        unreachable_count=sum(1 for s in states if s == DeviceState.UNREACHABLE),
        rebooting_count=sum(1 for s in states if s == DeviceState.REBOOTING),
        total_sites=len(w.sites),
        active_alerts=len(w.active_alerts),
        global_failure_multiplier=w.global_failure_multiplier,
        tick_count=w.tick_count,
    )


# ---------------------------------------------------------------------------
# REST routes
# ---------------------------------------------------------------------------

@app.get("/world", response_model=WorldSummaryOut)
async def get_world():
    return _build_summary()


@app.get("/sites")
async def get_sites() -> list[SiteOut]:
    engine = _get_engine()
    result = []
    for site in engine.world.sites.values():
        devices_in_site = [engine.world.devices[did] for did in site.device_ids if did in engine.world.devices]
        result.append(SiteOut(
            id=site.id,
            name=site.name,
            site_type=site.site_type,
            city=site.city,
            state_code=site.state_code,
            employee_count=site.employee_count,
            device_ids=site.device_ids,
            device_count=len(devices_in_site),
            healthy_count=sum(1 for d in devices_in_site if d.state == DeviceState.HEALTHY),
            impaired_count=sum(1 for d in devices_in_site if d.state != DeviceState.HEALTHY),
        ))
    return result


@app.get("/devices", response_model=list[DeviceOut])
async def get_devices(
    site_id: Optional[str] = None,
    state: Optional[str] = None,
    vendor: Optional[str] = None,
    category: Optional[str] = None,
):
    engine = _get_engine()
    devices = list(engine.world.devices.values())

    if site_id:
        devices = [d for d in devices if d.location.site_id == site_id]
    if state:
        devices = [d for d in devices if d.state.value == state]
    if vendor:
        devices = [d for d in devices if d.vendor.lower() == vendor.lower()]
    if category:
        devices = [d for d in devices if d.category.value == category]

    return [DeviceOut.from_instance(d) for d in devices]


@app.get("/devices/{device_id}", response_model=DeviceOut)
async def get_device(device_id: str):
    engine = _get_engine()
    device = engine.world.devices.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceOut.from_instance(device)


@app.get("/topology", response_model=TopologyOut)
async def get_topology(site_id: Optional[str] = None):
    engine = _get_engine()
    devices = list(engine.world.devices.values())
    if site_id:
        devices = [d for d in devices if d.location.site_id == site_id]

    nodes = [
        TopologyNode(
            id=d.id,
            label=d.hostname,
            category=d.category.value,
            state=d.state.value,
            vendor=d.vendor,
            site_id=d.location.site_id,
            site_name=d.location.site_name,
            parent_id=d.parent_id,
            is_consumer_grade=d.sku.is_consumer_grade,
        )
        for d in devices
    ]
    edges = [
        TopologyEdge(source=d.parent_id, target=d.id)
        for d in devices
        if d.parent_id and d.parent_id in engine.world.devices
    ]

    return TopologyOut(nodes=nodes, edges=edges)


@app.get("/alerts", response_model=list[AlertOut])
async def get_alerts(limit: int = 100, severity: Optional[str] = None):
    engine = _get_engine()
    alerts = list(reversed(engine.world.active_alerts))
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    return [
        AlertOut(
            id=a.id,
            timestamp=a.timestamp,
            sim_time=a.sim_time,
            event_type=a.event_type,
            device_id=a.device_id,
            hostname=a.hostname,
            vendor=a.vendor,
            site_name=a.site_name,
            failure_mode_id=a.failure_mode_id,
            severity=a.severity,
            message=a.message,
            is_manual=a.is_manual,
            cascade_from_device_id=a.cascade_from_device_id,
            previous_state=a.previous_state,
            new_state=a.new_state,
        )
        for a in alerts[:limit]
    ]


@app.get("/failure-modes")
async def get_failure_modes():
    return [
        {
            "id": fm.id,
            "name": fm.name,
            "description": fm.description,
            "severity": fm.severity,
            "base_prob_per_hour": fm.base_prob_per_hour,
            "resulting_state": fm.resulting_state,
            "mttr_hours_range": list(fm.mttr_hours_range),
            "cascades_downstream": fm.cascades_downstream,
            "vendor_specific_notes": fm.vendor_specific_notes,
        }
        for fm in FAILURE_MODES.values()
    ]


@app.get("/skus")
async def get_skus():
    return [
        {
            "id": sku_id,
            "vendor": sku.vendor,
            "product_line": sku.product_line,
            "model": sku.model,
            "category": sku.category.value,
            "api_protocol": sku.api.protocol.value,
            "is_consumer_grade": sku.is_consumer_grade,
            "mtbf_hours": sku.mtbf_hours,
            "failure_mode_ids": sku.failure_mode_ids,
            "api_quirks": sku.api.quirks,
        }
        for sku_id, sku in DEVICE_SKUS.items()
    ]


# ---------------------------------------------------------------------------
# Chaos injection
# ---------------------------------------------------------------------------

@app.post("/chaos/inject", response_model=AlertOut)
async def chaos_inject(req: ChaosInjectRequest):
    engine = _get_engine()
    if req.device_id not in engine.world.devices:
        raise HTTPException(status_code=404, detail="Device not found")
    if req.failure_mode_id not in FAILURE_MODES:
        raise HTTPException(status_code=400, detail="Unknown failure mode")
    device = engine.world.devices[req.device_id]
    if req.failure_mode_id not in device.sku.failure_mode_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Failure mode '{req.failure_mode_id}' not applicable to {device.model}",
        )
    event = engine.inject_failure(req.device_id, req.failure_mode_id)
    return AlertOut(
        id=event.id, timestamp=event.timestamp, sim_time=event.sim_time,
        event_type=event.event_type, device_id=event.device_id, hostname=event.hostname,
        vendor=event.vendor, site_name=event.site_name, failure_mode_id=event.failure_mode_id,
        severity=event.severity, message=event.message, is_manual=event.is_manual,
        cascade_from_device_id=event.cascade_from_device_id,
        previous_state=event.previous_state, new_state=event.new_state,
    )


@app.post("/chaos/pattern")
async def chaos_pattern(req: ChaosPatternRequest):
    engine = _get_engine()
    valid_patterns = {"thundering_herd", "rack_outage", "wan_flap", "bad_firmware", "rolling_reboot"}
    if req.pattern not in valid_patterns:
        raise HTTPException(status_code=400, detail=f"Unknown pattern. Valid: {valid_patterns}")
    events = engine.trigger_pattern(req.pattern, site_id=req.site_id, target_vendor=req.target_vendor)
    return {"triggered": len(events), "pattern": req.pattern, "events": [e.id for e in events]}


# ---------------------------------------------------------------------------
# Device actions
# ---------------------------------------------------------------------------

@app.post("/devices/{device_id}/reboot", response_model=AlertOut)
async def reboot_device(device_id: str):
    engine = _get_engine()
    if device_id not in engine.world.devices:
        raise HTTPException(status_code=404, detail="Device not found")
    event = engine.reboot_device(device_id)
    return AlertOut(
        id=event.id, timestamp=event.timestamp, sim_time=event.sim_time,
        event_type=event.event_type, device_id=event.device_id, hostname=event.hostname,
        vendor=event.vendor, site_name=event.site_name, failure_mode_id=event.failure_mode_id,
        severity=event.severity, message=event.message, is_manual=event.is_manual,
        cascade_from_device_id=event.cascade_from_device_id,
        previous_state=event.previous_state, new_state=event.new_state,
    )


@app.post("/devices/{device_id}/maintenance")
async def set_maintenance(device_id: str, enable: bool = True):
    engine = _get_engine()
    if device_id not in engine.world.devices:
        raise HTTPException(status_code=404, detail="Device not found")
    event = engine.set_maintenance(device_id, enable)
    return {"success": True, "device_id": device_id, "maintenance": enable, "event_id": event.id}


@app.post("/devices/{device_id}/api/{action}", response_model=RemedyActionResult)
async def device_api_call(device_id: str, action: str, payload: Optional[dict] = None):
    """Simulate a vendor API call against a device. Returns vendor-specific response."""
    engine = _get_engine()
    device = engine.world.devices.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    result = await api_call(device, action, payload)
    return result


# ---------------------------------------------------------------------------
# Simulation control
# ---------------------------------------------------------------------------

@app.post("/sim/control")
async def sim_control(req: SimControlRequest):
    engine = _get_engine()
    world = engine.world

    if req.action == "play":
        world.clock.is_running = True
    elif req.action == "pause":
        world.clock.is_running = False
    elif req.action == "set_speed":
        if req.speed is None or req.speed <= 0:
            raise HTTPException(status_code=400, detail="speed must be > 0")
        world.clock.speed_multiplier = req.speed
    elif req.action == "reset":
        await engine.stop()
        new_world = generate_world(seed=world.seed)
        engine.world = new_world
        await engine.start()
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    return {"action": req.action, "speed": world.clock.speed_multiplier, "running": world.clock.is_running}


@app.post("/sim/failure-multiplier")
async def set_failure_multiplier(multiplier: float):
    if multiplier < 0.0 or multiplier > 20.0:
        raise HTTPException(status_code=400, detail="multiplier must be between 0 and 20")
    engine = _get_engine()
    engine.world.global_failure_multiplier = multiplier
    return {"global_failure_multiplier": multiplier}


@app.post("/sim/seed/{seed}")
async def change_seed(seed: int):
    """Regenerate the world with a new seed."""
    engine = _get_engine()
    await engine.stop()
    new_world = generate_world(seed=seed)
    engine.world = new_world
    await engine.start()
    return {"seed": seed, "devices": len(new_world.devices), "sites": len(new_world.sites)}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(_ws_clients))

    try:
        # Send full world snapshot on connect
        engine = _get_engine()
        snapshot = {
            "type": "world_snapshot",
            "data": {
                "summary": _build_summary().model_dump(mode="json"),
                "devices": [DeviceOut.from_instance(d).model_dump(mode="json")
                            for d in engine.world.devices.values()],
                "sites": [
                    {
                        "id": s.id, "name": s.name, "site_type": s.site_type,
                        "city": s.city, "state_code": s.state_code,
                        "employee_count": s.employee_count,
                        "device_ids": s.device_ids,
                    }
                    for s in engine.world.sites.values()
                ],
                "topology": (await get_topology()).model_dump(mode="json"),
            },
        }
        await ws.send_text(json.dumps(snapshot, default=str))

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                msg = json.loads(data)
                # Handle ping
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "ping"}))

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        _ws_clients.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(_ws_clients))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("net_runner.api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
