"""Remediation engine — wires rules, ML, and LLM together.

Receives NetworkState updates from the SourceConnector, runs analysis,
and calls back to the connector to execute approved actions.
No dependency on any specific IT source.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Optional

from .agent import LLMAgent
from .connector import SourceConnector
from .ml import BROADCAST_EVERY, MLRiskScorer
from .models import (
    ActionStatus,
    ActionType,
    AgentThought,
    RemediationAction,
    RemediationConfig,
)
from .rules import BUILT_IN_RULES, Rule
from .schema import NetworkState

logger = logging.getLogger(__name__)

ACTION_HISTORY_LIMIT = 200


class RemediationEngine:
    def __init__(self, connector: SourceConnector) -> None:
        self._connector = connector
        self.config = RemediationConfig(
            rules_status={r.id: r.enabled for r in BUILT_IN_RULES},
        )
        self._rules: list[Rule] = list(BUILT_IN_RULES)
        self._actions: list[RemediationAction] = []
        self._ml = MLRiskScorer()
        self._agent = LLMAgent()
        self._risk_scores: dict[str, int] = {}
        self._last_thought: Optional[AgentThought] = None
        self._tick_count = 0

        # Broadcast callbacks — registered by the API layer
        self._on_action: list[Callable[[RemediationAction], Any]] = []
        self._on_ml_scores: list[Callable[[dict[str, int]], Any]] = []
        self._on_agent_thought: list[Callable[[AgentThought], Any]] = []
        self._on_config: list[Callable[[RemediationConfig], Any]] = []

        connector.on_update(self._on_network_update)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def on_action(self, cb: Callable[[RemediationAction], Any]) -> None:
        self._on_action.append(cb)

    def on_ml_scores(self, cb: Callable[[dict[str, int]], Any]) -> None:
        self._on_ml_scores.append(cb)

    def on_agent_thought(self, cb: Callable[[AgentThought], Any]) -> None:
        self._on_agent_thought.append(cb)

    def on_config(self, cb: Callable[[RemediationConfig], Any]) -> None:
        self._on_config.append(cb)

    def _emit(self, callbacks: list[Callable], payload: Any) -> None:
        for cb in callbacks:
            try:
                result = cb(payload)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception as exc:
                logger.warning("callback error: %s", exc)

    # ------------------------------------------------------------------
    # Network state update handler (called by connector on every change)
    # ------------------------------------------------------------------

    def _on_network_update(self, state: NetworkState) -> None:
        tick = state.tick_count
        # Avoid running rules multiple times for the same tick
        if tick == self._tick_count and tick != 0:
            return
        self._tick_count = tick

        if self.config.ml_enabled:
            self._ml.update(state)
            if tick % BROADCAST_EVERY == 0:
                self._risk_scores = self._ml.score_all(state)
                self._emit(self._on_ml_scores, dict(self._risk_scores))

        if self.config.rules_enabled:
            for rule in self._rules:
                cfg_enabled = self.config.rules_status.get(rule.id, rule.enabled)
                for device in state.devices.values():
                    action = rule.evaluate(device, state, tick, cfg_enabled)
                    if action:
                        self._enqueue(action, state)

        if (
            self.config.llm_enabled
            and self.config.llm_auto_trigger
            and self._agent.is_available()
            and self._agent.should_auto_trigger(state)
        ):
            asyncio.ensure_future(self._run_agent(state))

    # ------------------------------------------------------------------
    # Action lifecycle
    # ------------------------------------------------------------------

    def _enqueue(self, action: RemediationAction, state: NetworkState) -> None:
        effective_auto = action.auto_execute and not self.config.human_in_loop
        if effective_auto:
            action.status = ActionStatus.AUTO
            action.approved_by = "auto"
            asyncio.ensure_future(self._execute(action, state))
        else:
            action.status = ActionStatus.PENDING
            self._append(action)
            self._emit(self._on_action, action)
            logger.info("Action queued [%s]: %s on %s", action.rule_id, action.action_type.value, action.hostname)

    def approve(self, action_id: str) -> Optional[RemediationAction]:
        action = self._find(action_id)
        if action is None or action.status != ActionStatus.PENDING:
            return None
        action.status = ActionStatus.APPROVED
        action.approved_by = "human"
        asyncio.ensure_future(self._execute(action, self._connector.state))
        return action

    def reject(self, action_id: str) -> Optional[RemediationAction]:
        action = self._find(action_id)
        if action is None or action.status != ActionStatus.PENDING:
            return None
        action.status = ActionStatus.REJECTED
        self._emit(self._on_action, action)
        return action

    async def _execute(self, action: RemediationAction, state: NetworkState) -> None:
        action.status = ActionStatus.EXECUTING
        action.executed_at = datetime.utcnow()
        self._append(action)
        self._emit(self._on_action, action)

        if action.action_type == ActionType.ALERT:
            action.result = "Alert surfaced — no device action taken"
            action.status = ActionStatus.DONE
            self._emit(self._on_action, action)
            return

        if action.device_id not in state.devices:
            action.status = ActionStatus.FAILED
            action.result = "Device not found in current network state"
            self._emit(self._on_action, action)
            return

        try:
            if action.action_type == ActionType.REBOOT:
                action.result = await self._connector.reboot(action.device_id)
            elif action.action_type == ActionType.MAINTENANCE_ON:
                action.result = await self._connector.maintenance_on(action.device_id)
            elif action.action_type == ActionType.MAINTENANCE_OFF:
                action.result = await self._connector.maintenance_off(action.device_id)
            action.status = ActionStatus.DONE
        except Exception as exc:
            action.status = ActionStatus.FAILED
            action.result = str(exc)
            logger.error("Action execution failed [%s]: %s", action.id, exc)

        self._emit(self._on_action, action)

    # ------------------------------------------------------------------
    # LLM agent
    # ------------------------------------------------------------------

    async def _run_agent(self, state: NetworkState) -> None:
        logger.info("LLM agent triggered (tick=%d)", state.tick_count)
        async for thought in self._agent.analyse(state, self._actions):
            self._last_thought = thought
            self._emit(self._on_agent_thought, thought)
            if thought.is_complete:
                proposals = self._agent.parse_proposals(thought, state)
                for p in proposals:
                    self._enqueue(p, state)

    async def trigger_agent(self) -> None:
        if not self._agent.is_available():
            raise ValueError("ANTHROPIC_API_KEY not configured")
        await self._run_agent(self._connector.state)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_actions(self, status: Optional[str] = None, limit: int = 50) -> list[RemediationAction]:
        actions = self._actions
        if status:
            actions = [a for a in actions if a.status.value == status]
        return list(reversed(actions[-limit:]))

    def get_risk_scores(self) -> dict[str, int]:
        return dict(self._risk_scores)

    def get_rules(self) -> list[dict]:
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "severity": r.severity,
                "action_type": r.action_type.value,
                "auto_execute": r.auto_execute,
                "cooldown_ticks": r.cooldown_ticks,
                "enabled": self.config.rules_status.get(r.id, r.enabled),
            }
            for r in self._rules
        ]

    def get_agent_status(self) -> dict:
        return {
            "available": self._agent.is_available(),
            "running": self._agent._running,
            "last_triggered": (
                self._agent._last_triggered.isoformat()
                if self._agent._last_triggered else None
            ),
        }

    # ------------------------------------------------------------------
    # Config mutations
    # ------------------------------------------------------------------

    def update_config(self, patch: dict) -> RemediationConfig:
        for key in ("human_in_loop", "rules_enabled", "ml_enabled",
                    "llm_enabled", "llm_auto_trigger"):
            if key in patch:
                setattr(self.config, key, bool(patch[key]))
        if "rules_status" in patch and isinstance(patch["rules_status"], dict):
            self.config.rules_status.update(patch["rules_status"])
        self._emit(self._on_config, self.config)
        return self.config

    def toggle_rule(self, rule_id: str, enabled: bool) -> bool:
        if not any(r.id == rule_id for r in self._rules):
            return False
        self.config.rules_status[rule_id] = enabled
        self._emit(self._on_config, self.config)
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _append(self, action: RemediationAction) -> None:
        if action not in self._actions:
            self._actions.append(action)
        if len(self._actions) > ACTION_HISTORY_LIMIT:
            self._actions = self._actions[-ACTION_HISTORY_LIMIT:]

    def _find(self, action_id: str) -> Optional[RemediationAction]:
        for a in self._actions:
            if a.id == action_id:
                return a
        return None
