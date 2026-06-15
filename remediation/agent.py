"""LLM-powered NOC analyst agent.

Source-agnostic: builds context from NetworkState and proposes remediation
actions via structured output.  Streams chunks so the frontend shows live typing.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import AsyncIterator, Optional

from .models import ActionType, AgentThought, AgentType, RemediationAction
from .schema import NetworkState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NOC-ANALYST, an expert network operations center analyst.
You are given a real-time snapshot of IT infrastructure and must:

1. Identify the most likely root cause(s) of current incidents.
2. Detect systemic patterns (cascades, vendor-specific issues, site-wide outages).
3. Propose specific, targeted remediation actions ranked by priority.

When proposing actions, use this exact format on its own line:
  ACTION: <action_type> DEVICE: <device_id> REASON: <one-line reason>

Valid action types: reboot, maintenance_on, maintenance_off

Be concise. Lead with the most impactful finding. Use bullet points for clarity.
Avoid restating obvious facts already visible in the data."""


def _build_context(state: NetworkState, recent_actions: list[RemediationAction]) -> str:
    lines = [
        f"## Network State (tick {state.tick_count}) — source: {state.source_url}",
        "",
        "### Device Health Summary",
    ]
    by_state = state.devices_by_state()
    for s, devs in sorted(by_state.items()):
        lines.append(f"  {s}: {len(devs)}")

    impaired = state.impaired_devices()
    impaired.sort(key=lambda d: {
        "failed": 0, "unreachable": 1, "rebooting": 2, "degraded": 3, "recovering": 4,
    }.get(d.state, 5))

    if impaired:
        lines.append("")
        lines.append(f"### Impaired Devices ({len(impaired)})")
        for d in impaired[:30]:
            modes = ", ".join(d.active_failure_modes) if d.active_failure_modes else "—"
            parent = f" [parent: {d.parent_id}]" if d.parent_id else ""
            lines.append(
                f"  [{d.state.upper():12s}] {d.hostname} ({d.category})"
                f" @ {d.site_name}{parent} | failures: {modes}"
            )
        if len(impaired) > 30:
            lines.append(f"  ... and {len(impaired) - 30} more")

    if state.recent_alerts:
        shown = state.recent_alerts[-20:]
        lines.append("")
        lines.append(f"### Recent Alerts ({len(shown)} shown)")
        for a in reversed(shown):
            lines.append(f"  [{a.severity.upper():8s}] {a.sim_time} {a.hostname}: {a.message}")

    pending = [a for a in recent_actions if a.status.value in {"pending", "approved", "auto"}]
    if pending:
        lines.append("")
        lines.append(f"### Pending Remediation Actions ({len(pending)})")
        for a in pending[:10]:
            lines.append(f"  [{a.status.value}] {a.action_type.value} {a.hostname}: {a.reason[:80]}")

    return "\n".join(lines)


class LLMAgent:
    def __init__(self) -> None:
        self._client = None
        self._running = False
        self._last_triggered: Optional[datetime] = None
        self._min_interval_s = 30

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if not api_key:
                    logger.warning("ANTHROPIC_API_KEY not set — LLM agent disabled")
                    return None
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                logger.warning("anthropic package not installed — LLM agent disabled")
        return self._client

    def is_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def should_auto_trigger(self, state: NetworkState) -> bool:
        if self._running:
            return False
        if self._last_triggered:
            elapsed = (datetime.utcnow() - self._last_triggered).total_seconds()
            if elapsed < self._min_interval_s:
                return False
        return bool(state.critical_alerts())

    async def analyse(
        self,
        state: NetworkState,
        recent_actions: list[RemediationAction],
    ) -> AsyncIterator[AgentThought]:
        client = self._get_client()
        if client is None:
            yield AgentThought(
                content="⚠ LLM agent unavailable (ANTHROPIC_API_KEY not set).",
                is_complete=True,
            )
            return

        self._running = True
        self._last_triggered = datetime.utcnow()
        context = _build_context(state, recent_actions)
        accumulated = ""
        thought_id = None
        action_lines: list[str] = []

        try:
            import anthropic
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": context}],
            ) as stream:
                for text in stream.text_stream:
                    accumulated += text
                    thought = AgentThought(content=accumulated, is_complete=False)
                    if thought_id is None:
                        thought_id = thought.id
                    else:
                        thought.id = thought_id
                    yield thought
                    await asyncio.sleep(0)

            for line in accumulated.splitlines():
                m = re.match(
                    r"ACTION:\s*(\w+)\s+DEVICE:\s*(\S+)\s+REASON:\s*(.+)", line.strip()
                )
                if m:
                    action_lines.append(f"{m.group(1)}:{m.group(2)}:{m.group(3)}")

            final = AgentThought(
                content=accumulated,
                is_complete=True,
                actions_proposed=action_lines,
            )
            final.id = thought_id or final.id
            yield final

        except Exception as exc:
            err = AgentThought(content=f"⚠ Agent error: {exc}", is_complete=True)
            if thought_id:
                err.id = thought_id
            yield err
        finally:
            self._running = False

    def parse_proposals(
        self,
        thought: AgentThought,
        state: NetworkState,
    ) -> list[RemediationAction]:
        actions = []
        for line in thought.actions_proposed:
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            action_str, device_id, reason = parts
            if device_id not in state.devices:
                continue
            try:
                action_type = ActionType(action_str.lower())
            except ValueError:
                continue
            device = state.devices[device_id]
            actions.append(RemediationAction(
                agent_type=AgentType.LLM,
                device_id=device_id,
                hostname=device.hostname,
                site_name=device.site_name,
                action_type=action_type,
                reason=reason.strip(),
                severity="medium",
                auto_execute=False,    # LLM proposals always need human sign-off
            ))
        return actions
