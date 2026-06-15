"""Built-in rules engine.

Each Rule evaluates a condition against a DeviceSnapshot every tick.
A per-device cooldown prevents the same rule from spamming on the same device.
Rules are source-agnostic — they work on generic NetworkState objects.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from .models import ActionType, AgentType, RemediationAction
from .schema import DeviceSnapshot, NetworkState

logger = logging.getLogger(__name__)

_LEAF = {"wap", "endpoint", "phone", "printer"}
_CORE = {"switch_core", "wan_edge", "router", "firewall"}


@dataclass
class Rule:
    id: str
    name: str
    description: str
    severity: str
    action_type: ActionType
    condition: Callable[[DeviceSnapshot, NetworkState], bool]
    reason_template: str
    auto_execute: bool = False
    cooldown_ticks: int = 20
    enabled: bool = True
    _last_fired: dict[str, int] = field(default_factory=dict, repr=False)

    def evaluate(
        self,
        device: DeviceSnapshot,
        state: NetworkState,
        tick: int,
        config_enabled: bool,
    ) -> Optional[RemediationAction]:
        if not self.enabled or not config_enabled:
            return None
        last = self._last_fired.get(device.id, -self.cooldown_ticks)
        if tick - last < self.cooldown_ticks:
            return None
        if not self.condition(device, state):
            return None

        self._last_fired[device.id] = tick
        reason = self.reason_template.format(
            hostname=device.hostname,
            state=device.state,
            site=device.site_name,
        )
        return RemediationAction(
            rule_id=self.id,
            agent_type=AgentType.RULES,
            device_id=device.id,
            hostname=device.hostname,
            site_name=device.site_name,
            action_type=self.action_type,
            reason=reason,
            severity=self.severity,
            auto_execute=self.auto_execute,
        )


BUILT_IN_RULES: list[Rule] = [
    Rule(
        id="wap_unreachable_reboot",
        name="WAP unreachable → reboot",
        description=(
            "Automatically reboots a WAP that becomes unreachable. "
            "Low blast radius — WAPs are leaf devices with no downstream dependencies."
        ),
        severity="low",
        action_type=ActionType.REBOOT,
        condition=lambda d, _s: d.category == "wap" and d.state == "unreachable",
        reason_template="{hostname} is unreachable — scheduling automatic reboot to restore connectivity.",
        auto_execute=True,
        cooldown_ticks=30,
    ),
    Rule(
        id="leaf_failed_reboot",
        name="Leaf device failed → reboot",
        description=(
            "Reboots failed leaf devices (endpoints, phones, printers). "
            "Safe to auto-execute — no downstream cascade risk."
        ),
        severity="low",
        action_type=ActionType.REBOOT,
        condition=lambda d, _s: d.category in _LEAF and d.state == "failed",
        reason_template="{hostname} has failed — auto-reboot scheduled (leaf device, no downstream risk).",
        auto_execute=True,
        cooldown_ticks=40,
    ),
    Rule(
        id="high_error_rate_reboot",
        name="Sustained high error rate → reboot",
        description="Reboots any non-core device sustaining >25% interface error rate.",
        severity="medium",
        action_type=ActionType.REBOOT,
        condition=lambda d, _s: (
            d.category not in _CORE
            and d.state in {"healthy", "degraded"}
            and d.metrics.error_rate > 25.0
        ),
        reason_template="{hostname} has a {state} state with error rate >25% — reboot to clear interface errors.",
        auto_execute=False,
        cooldown_ticks=24,
    ),
    Rule(
        id="memory_critical_alert",
        name="Critical memory pressure → alert",
        description=(
            "Raises an alert when memory utilization exceeds 90%. "
            "Does not auto-reboot — ops team should investigate for memory leaks."
        ),
        severity="high",
        action_type=ActionType.ALERT,
        condition=lambda d, _s: (
            d.state in {"healthy", "degraded"}
            and d.metrics.memory_utilization > 90.0
        ),
        reason_template="{hostname} memory >90% — investigate for memory leak or over-subscription.",
        auto_execute=True,
        cooldown_ticks=60,
    ),
    Rule(
        id="access_sw_failed_maintenance",
        name="Access switch failed → maintenance mode",
        description=(
            "Puts a failed access switch into maintenance so it stops generating cascade alerts "
            "while the ops team dispatches."
        ),
        severity="high",
        action_type=ActionType.MAINTENANCE_ON,
        condition=lambda d, _s: d.category == "switch_access" and d.state == "failed",
        reason_template=(
            "{hostname} access switch has failed — placing in maintenance to suppress "
            "downstream cascade alerts until on-site remediation."
        ),
        auto_execute=False,
        cooldown_ticks=50,
    ),
    Rule(
        id="core_failed_escalate",
        name="Core device failed → critical escalation",
        description=(
            "Emits a critical alert when a core switch, WAN edge, firewall, or router fails. "
            "Requires manual approval for any further action."
        ),
        severity="critical",
        action_type=ActionType.ALERT,
        condition=lambda d, _s: d.category in _CORE and d.state in {"failed", "unreachable"},
        reason_template=(
            "{hostname} ({state}) is a core device — site {site} may be experiencing "
            "widespread connectivity loss. Immediate escalation required."
        ),
        auto_execute=True,    # alert-only is always safe to surface
        cooldown_ticks=60,
    ),
]
