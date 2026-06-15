"""Source connector — bridges the remediation engine to any IT monitoring source.

Connects to the source via WebSocket (receives device/alert updates) and REST
(executes actions like reboot, maintenance).  The connector is the only place
that knows the source's URL or protocol — the rules/ML/agent layers never touch it.

Environment variable:
  SIMULATOR_URL   Base HTTP URL of the IT source (default: http://localhost:8000)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Callable, Optional

import httpx
import websockets
import websockets.exceptions

from .schema import AlertSnapshot, DeviceSnapshot, NetworkState

logger = logging.getLogger(__name__)

MAX_ALERTS = 200


class SourceConnector:
    """Connects to one IT monitoring source.  Call start() to begin streaming."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self._base_url = (base_url or os.environ.get("SIMULATOR_URL", "http://localhost:8000")).rstrip("/")
        self._ws_url = self._base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        self._state = NetworkState(source_url=self._base_url)
        self._http = httpx.AsyncClient(base_url=self._base_url, timeout=10.0)
        self._on_update: list[Callable[[NetworkState], None]] = []
        self._on_alert: list[Callable[[AlertSnapshot], None]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def state(self) -> NetworkState:
        return self._state

    @property
    def source_url(self) -> str:
        return self._base_url

    def on_update(self, cb: Callable[[NetworkState], None]) -> None:
        self._on_update.append(cb)

    def on_alert(self, cb: Callable[[AlertSnapshot], None]) -> None:
        self._on_alert.append(cb)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Action execution — calls source REST endpoints
    # ------------------------------------------------------------------

    async def reboot(self, device_id: str) -> str:
        r = await self._http.post(f"/devices/{device_id}/reboot")
        r.raise_for_status()
        return "Reboot command sent"

    async def maintenance_on(self, device_id: str) -> str:
        r = await self._http.post(f"/devices/{device_id}/maintenance?enable=true")
        r.raise_for_status()
        return "Maintenance mode enabled"

    async def maintenance_off(self, device_id: str) -> str:
        r = await self._http.post(f"/devices/{device_id}/maintenance?enable=false")
        r.raise_for_status()
        return "Maintenance mode disabled"

    # ------------------------------------------------------------------
    # WebSocket loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        backoff = 2.0
        while self._running:
            try:
                logger.info("Connecting to source: %s", self._ws_url)
                async with websockets.connect(self._ws_url, ping_interval=20) as ws:
                    backoff = 2.0
                    logger.info("Connected to source WebSocket")
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw)
                            self._handle(msg)
                        except Exception as exc:
                            logger.debug("WS message parse error: %s", exc)
            except (websockets.exceptions.WebSocketException, OSError, asyncio.TimeoutError) as exc:
                if not self._running:
                    break
                logger.warning("Source WS disconnected (%s) — reconnect in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    def _handle(self, msg: dict) -> None:
        t = msg.get("type")
        data = msg.get("data", {})

        if t == "world_snapshot":
            devices_raw = data.get("devices") or []
            self._state.devices = {
                d["id"]: DeviceSnapshot.from_dict(d) for d in devices_raw
            }
            alerts_raw = data.get("alerts") or []
            self._state.recent_alerts = [AlertSnapshot.from_dict(a) for a in alerts_raw][-MAX_ALERTS:]
            self._notify_update()

        elif t == "device_update":
            snap = DeviceSnapshot.from_dict(data)
            self._state.devices[snap.id] = snap
            self._notify_update()

        elif t == "alert":
            alert = AlertSnapshot.from_dict(data)
            self._state.recent_alerts.append(alert)
            if len(self._state.recent_alerts) > MAX_ALERTS:
                self._state.recent_alerts = self._state.recent_alerts[-MAX_ALERTS:]
            for cb in self._on_alert:
                try:
                    cb(alert)
                except Exception as exc:
                    logger.warning("alert callback error: %s", exc)
            self._notify_update()

        elif t == "tick":
            self._state.tick_count = data.get("tick_count", self._state.tick_count)
            self._notify_update()

        elif t == "ping":
            pass  # handled by websockets library keep-alive

    def _notify_update(self) -> None:
        for cb in self._on_update:
            try:
                result = cb(self._state)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception as exc:
                logger.warning("update callback error: %s", exc)
