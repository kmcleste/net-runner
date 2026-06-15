"""Remediation data models — no dependency on any specific IT source."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    REBOOT = "reboot"
    MAINTENANCE_ON = "maintenance_on"
    MAINTENANCE_OFF = "maintenance_off"
    ALERT = "alert"           # surface alert only; no device mutation


class ActionStatus(str, Enum):
    PENDING = "pending"       # awaiting human approval
    APPROVED = "approved"     # human-approved, queued
    AUTO = "auto"             # auto-approved (HiL off), queued
    REJECTED = "rejected"
    EXECUTING = "executing"
    DONE = "done"
    FAILED = "failed"


class AgentType(str, Enum):
    RULES = "rules"
    ML = "ml"
    LLM = "llm"


@dataclass
class RemediationAction:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: datetime = field(default_factory=datetime.utcnow)
    rule_id: Optional[str] = None
    agent_type: AgentType = AgentType.RULES
    device_id: str = ""
    hostname: str = ""
    site_name: str = ""
    action_type: ActionType = ActionType.ALERT
    reason: str = ""
    severity: str = "medium"
    auto_execute: bool = False   # per-action flag; overridden by global HiL
    status: ActionStatus = ActionStatus.PENDING
    approved_by: Optional[str] = None   # "human" | "auto"
    executed_at: Optional[datetime] = None
    result: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "rule_id": self.rule_id,
            "agent_type": self.agent_type.value,
            "device_id": self.device_id,
            "hostname": self.hostname,
            "site_name": self.site_name,
            "action_type": self.action_type.value,
            "reason": self.reason,
            "severity": self.severity,
            "auto_execute": self.auto_execute,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "result": self.result,
        }


@dataclass
class AgentThought:
    """A chunk of streaming LLM agent output."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    content: str = ""
    is_complete: bool = False
    actions_proposed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "is_complete": self.is_complete,
            "actions_proposed": self.actions_proposed,
        }


@dataclass
class RemediationConfig:
    human_in_loop: bool = True        # Global: all actions require human approval
    rules_enabled: bool = True
    ml_enabled: bool = True
    llm_enabled: bool = True
    llm_auto_trigger: bool = True     # LLM wakes on critical alerts automatically
    rules_status: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "human_in_loop": self.human_in_loop,
            "rules_enabled": self.rules_enabled,
            "ml_enabled": self.ml_enabled,
            "llm_enabled": self.llm_enabled,
            "llm_auto_trigger": self.llm_auto_trigger,
            "rules_status": self.rules_status,
        }
