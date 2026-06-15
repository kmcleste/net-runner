"""Generic IT infrastructure state models.

These mirror the shape of data emitted by the net-runner simulator WebSocket,
but are deliberately kept vendor-neutral so this app can plug into any source
that speaks the same JSON contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeviceMetricsSnapshot:
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    uptime_hours: float = 0.0
    client_count: Optional[int] = None
    interface_utilization: dict[str, float] = field(default_factory=dict)
    packets_per_second: float = 0.0
    error_rate: float = 0.0


@dataclass
class DeviceSnapshot:
    id: str
    hostname: str
    vendor: str
    model: str
    category: str          # wap, switch_core, router, firewall, …
    state: str             # healthy, degraded, failed, unreachable, rebooting, …
    site_id: str
    site_name: str
    parent_id: Optional[str]
    age_years: float
    is_consumer_grade: bool
    failure_count_24h: int
    active_failure_modes: list[str]
    metrics: DeviceMetricsSnapshot = field(default_factory=DeviceMetricsSnapshot)

    @classmethod
    def from_dict(cls, d: dict) -> DeviceSnapshot:
        m = d.get("metrics") or {}
        return cls(
            id=d["id"],
            hostname=d["hostname"],
            vendor=d.get("vendor", ""),
            model=d.get("model", ""),
            category=d.get("category", ""),
            state=d.get("state", "healthy"),
            site_id=(d.get("location") or {}).get("site_id", ""),
            site_name=(d.get("location") or {}).get("site_name", ""),
            parent_id=d.get("parent_id"),
            age_years=d.get("age_years", 0.0),
            is_consumer_grade=d.get("is_consumer_grade", False),
            failure_count_24h=d.get("failure_count_24h", 0),
            active_failure_modes=d.get("active_failure_modes") or [],
            metrics=DeviceMetricsSnapshot(
                cpu_utilization=m.get("cpu_utilization", 0.0),
                memory_utilization=m.get("memory_utilization", 0.0),
                uptime_hours=m.get("uptime_hours", 0.0),
                client_count=m.get("client_count"),
                interface_utilization=m.get("interface_utilization") or {},
                packets_per_second=m.get("packets_per_second", 0.0),
                error_rate=m.get("error_rate", 0.0),
            ),
        )


@dataclass
class AlertSnapshot:
    id: str
    sim_time: str
    event_type: str
    device_id: str
    hostname: str
    site_name: str
    severity: str          # low, medium, high, critical
    message: str
    is_manual: bool = False
    cascade_from_device_id: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> AlertSnapshot:
        return cls(
            id=d["id"],
            sim_time=d.get("sim_time", ""),
            event_type=d.get("event_type", ""),
            device_id=d.get("device_id", ""),
            hostname=d.get("hostname", ""),
            site_name=d.get("site_name", ""),
            severity=d.get("severity", "low"),
            message=d.get("message", ""),
            is_manual=d.get("is_manual", False),
            cascade_from_device_id=d.get("cascade_from_device_id"),
            previous_state=d.get("previous_state"),
            new_state=d.get("new_state"),
        )


@dataclass
class NetworkState:
    """Point-in-time snapshot of the monitored infrastructure."""
    devices: dict[str, DeviceSnapshot] = field(default_factory=dict)
    recent_alerts: list[AlertSnapshot] = field(default_factory=list)
    tick_count: int = 0
    source_url: str = ""

    # Convenience helpers used by rules/ML/agent
    def impaired_devices(self) -> list[DeviceSnapshot]:
        return [d for d in self.devices.values() if d.state not in {"healthy", "maintenance"}]

    def critical_alerts(self) -> list[AlertSnapshot]:
        return [a for a in self.recent_alerts if a.severity == "critical" and not a.is_manual]

    def devices_by_state(self) -> dict[str, list[DeviceSnapshot]]:
        result: dict[str, list[DeviceSnapshot]] = {}
        for d in self.devices.values():
            result.setdefault(d.state, []).append(d)
        return result
