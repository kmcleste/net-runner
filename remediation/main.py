"""Standalone remediation service.

Runs as a separate process/container.  Connects to any compatible IT source
(default: net-runner simulator at SIMULATOR_URL) and exposes:

  REST   — action approve/reject, config, rules, risk scores
  WS /ws — real-time stream of actions, ML scores, agent thoughts

Environment variables:
  SIMULATOR_URL       HTTP base URL of the IT source   (default: http://localhost:8000)
  ANTHROPIC_API_KEY   Enables the LLM agent
  PORT                Listen port                       (default: 9000)
  ALLOWED_ORIGINS     Comma-separated CORS origins      (default: *)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .connector import SourceConnector
from .engine import RemediationEngine
from .models import AgentThought, RemediationAction, RemediationConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

_connector: Optional[SourceConnector] = None
_engine: Optional[RemediationEngine] = None
_ws_clients: set[WebSocket] = set()


async def _broadcast(payload: dict[str, Any]) -> None:
    if not _ws_clients:
        return
    msg = json.dumps(payload, default=str)
    dead: set[WebSocket] = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


def _make_callbacks(engine: RemediationEngine) -> None:
    def on_action(action: RemediationAction) -> None:
        asyncio.ensure_future(_broadcast({"type": "action", "data": action.to_dict()}))

    def on_ml_scores(scores: dict[str, int]) -> None:
        asyncio.ensure_future(_broadcast({"type": "ml_scores", "data": scores}))

    def on_agent_thought(thought: AgentThought) -> None:
        asyncio.ensure_future(_broadcast({"type": "agent_thought", "data": thought.to_dict()}))

    def on_config(config: RemediationConfig) -> None:
        asyncio.ensure_future(_broadcast({"type": "config", "data": config.to_dict()}))

    engine.on_action(on_action)
    engine.on_ml_scores(on_ml_scores)
    engine.on_agent_thought(on_agent_thought)
    engine.on_config(on_config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _connector, _engine
    simulator_url = os.environ.get("SIMULATOR_URL", "http://localhost:8000")
    _connector = SourceConnector(base_url=simulator_url)
    _engine = RemediationEngine(_connector)
    _make_callbacks(_engine)
    await _connector.start()
    logger.info("Remediation service started — source: %s", simulator_url)
    yield
    await _connector.stop()


app = FastAPI(
    title="net-runner remediation",
    description="Standalone IT remediation engine",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_engine() -> RemediationEngine:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return _engine


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    _ws_clients.add(ws)
    engine = _get_engine()
    # Send current state on connect
    await ws.send_text(json.dumps({
        "type": "snapshot",
        "data": {
            "config": engine.config.to_dict(),
            "rules": engine.get_rules(),
            "actions": [a.to_dict() for a in engine.get_actions()],
            "agent": engine.get_agent_status(),
            "risk_scores": engine.get_risk_scores(),
            "source_url": _connector.source_url if _connector else "",
        },
    }, default=str))
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


# ---------------------------------------------------------------------------
# REST — health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "source_url": _connector.source_url if _connector else None,
        "source_connected": bool(_connector and _connector.state.devices),
    }


# ---------------------------------------------------------------------------
# REST — actions
# ---------------------------------------------------------------------------

@app.get("/actions")
async def list_actions(status: Optional[str] = None, limit: int = 50):
    return [a.to_dict() for a in _get_engine().get_actions(status=status, limit=limit)]


@app.post("/actions/{action_id}/approve")
async def approve_action(action_id: str):
    action = _get_engine().approve(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found or not pending")
    return action.to_dict()


@app.post("/actions/{action_id}/reject")
async def reject_action(action_id: str):
    action = _get_engine().reject(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found or not pending")
    return action.to_dict()


# ---------------------------------------------------------------------------
# REST — rules
# ---------------------------------------------------------------------------

@app.get("/rules")
async def list_rules():
    return _get_engine().get_rules()


@app.post("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: str, enabled: bool):
    ok = _get_engine().toggle_rule(rule_id, enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"rule_id": rule_id, "enabled": enabled}


# ---------------------------------------------------------------------------
# REST — config
# ---------------------------------------------------------------------------

@app.get("/config")
async def get_config():
    return _get_engine().config.to_dict()


@app.patch("/config")
async def patch_config(patch: dict):
    return _get_engine().update_config(patch).to_dict()


# ---------------------------------------------------------------------------
# REST — risk scores
# ---------------------------------------------------------------------------

@app.get("/risk-scores")
async def get_risk_scores():
    return _get_engine().get_risk_scores()


# ---------------------------------------------------------------------------
# REST — LLM agent
# ---------------------------------------------------------------------------

@app.get("/agent/status")
async def agent_status():
    return _get_engine().get_agent_status()


@app.post("/agent/trigger")
async def trigger_agent():
    engine = _get_engine()
    try:
        asyncio.ensure_future(engine.trigger_agent())
        return {"status": "triggered"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    port = int(os.environ.get("PORT", 9000))
    uvicorn.run("remediation.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
