"""Pydantic models for API serialization and core dataclasses for simulation state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from net_runner.catalog import DeviceCategory, DeviceSKU, DeviceState


# ---------------------------------------------------------------------------
# Simulation state (dataclasses — mutable, fast)
# ---------------------------------------------------------------------------

@dataclass
class Location:
    site_id: str
    site_name: str
    site_type: str       # "hq" | "regional" | "branch"
    building: str
    floor: int
    rack_id: Optional[str] = None
    rack_unit: Optional[int] = None


@dataclass
class DeviceMetrics:
    cpu_utilization: float = 0.0       # 0–100
    memory_utilization: float = 0.0    # 0–100
    uptime_hours: float = 0.0
    client_count: Optional[int] = None
    interface_utilization: dict[str, float] = field(default_factory=dict)
    packets_per_second: float = 0.0
    error_rate: float = 0.0            # interface error percentage


@dataclass
class DeviceInstance:
    id: str
    sku_id: str
    sku: DeviceSKU
    hostname: str
    firmware_version: str
    age_years: float
    location: Location
    state: DeviceState = DeviceState.HEALTHY
    parent_id: Optional[str] = None   # Upstream device (topology)
    ip_addresses: list[str] = field(default_factory=list)
    vlan_ids: list[int] = field(default_factory=list)
    metrics: DeviceMetrics = field(default_factory=DeviceMetrics)
    active_failure_modes: list[str] = field(default_factory=list)
    failure_count_24h: int = 0
    last_failure_at: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    failure_prob_modifier: float = 1.0   # Multiplier on base probabilities
    is_manually_failed: bool = False
    children_ids: list[str] = field(default_factory=list)

    @property
    def vendor(self) -> str:
        return self.sku.vendor

    @property
    def model(self) -> str:
        return self.sku.model

    @property
    def category(self) -> DeviceCategory:
        return self.sku.category

    @property
    def is_healthy(self) -> bool:
        return self.state == DeviceState.HEALTHY

    @property
    def is_impaired(self) -> bool:
        return self.state in (DeviceState.DEGRADED, DeviceState.FAILED,
                               DeviceState.UNREACHABLE, DeviceState.REBOOTING)


@dataclass
class Site:
    id: str
    name: str
    site_type: str   # "hq" | "regional" | "branch"
    city: str
    state_code: str
    employee_count: int
    buildings: int
    floors_per_building: int
    device_ids: list[str] = field(default_factory=list)

    @property
    def is_hq(self) -> bool:
        return self.site_type == "hq"


@dataclass
class SimEvent:
    id: str
    timestamp: datetime
    sim_time: datetime
    event_type: str       # "failure", "recovery", "alert", "manual_injection", "cascade"
    device_id: str
    hostname: str
    vendor: str
    site_name: str
    failure_mode_id: Optional[str]
    severity: str          # "low" | "medium" | "high" | "critical"
    message: str
    is_manual: bool = False
    cascade_from_device_id: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None


@dataclass
class SimClock:
    wall_start: datetime
    sim_start: datetime
    speed_multiplier: float = 1.0    # 1x = real time, 60x = 1 min/sec
    is_running: bool = True
    _elapsed_sim_seconds: float = 0.0

    @property
    def sim_now(self) -> datetime:
        from datetime import timedelta
        return self.sim_start + timedelta(seconds=self._elapsed_sim_seconds)

    def advance(self, real_seconds: float) -> float:
        """Advance clock by real_seconds. Returns simulated hours elapsed."""
        if not self.is_running:
            return 0.0
        sim_seconds = real_seconds * self.speed_multiplier
        self._elapsed_sim_seconds += sim_seconds
        return sim_seconds / 3600.0


@dataclass
class World:
    id: str
    seed: int
    org_name: str
    created_at: datetime
    clock: SimClock
    sites: dict[str, Site]
    devices: dict[str, DeviceInstance]
    events: list[SimEvent]
    active_alerts: list[SimEvent]
    global_failure_multiplier: float = 1.0
    tick_count: int = 0


# ---------------------------------------------------------------------------
# Pydantic models for API responses
# ---------------------------------------------------------------------------

class LocationOut(BaseModel):
    site_id: str
    site_name: str
    site_type: str
    building: str
    floor: int
    rack_id: Optional[str] = None
    rack_unit: Optional[int] = None


class MetricsOut(BaseModel):
    cpu_utilization: float
    memory_utilization: float
    uptime_hours: float
    client_count: Optional[int] = None
    interface_utilization: dict[str, float]
    packets_per_second: float
    error_rate: float


class DeviceOut(BaseModel):
    id: str
    sku_id: str
    hostname: str
    vendor: str
    product_line: str
    model: str
    category: str
    firmware_version: str
    age_years: float
    state: str
    location: LocationOut
    parent_id: Optional[str] = None
    ip_addresses: list[str]
    vlan_ids: list[int]
    metrics: MetricsOut
    active_failure_modes: list[str]
    failure_count_24h: int
    last_failure_at: Optional[datetime] = None
    api_protocol: str
    is_manually_failed: bool
    is_consumer_grade: bool
    children_ids: list[str]
    available_failure_modes: list[dict[str, Any]]

    @classmethod
    def from_instance(cls, d: DeviceInstance) -> "DeviceOut":
        from net_runner.catalog import FAILURE_MODES
        return cls(
            id=d.id,
            sku_id=d.sku_id,
            hostname=d.hostname,
            vendor=d.sku.vendor,
            product_line=d.sku.product_line,
            model=d.sku.model,
            category=d.sku.category.value,
            firmware_version=d.firmware_version,
            age_years=d.age_years,
            state=d.state.value,
            location=LocationOut(
                site_id=d.location.site_id,
                site_name=d.location.site_name,
                site_type=d.location.site_type,
                building=d.location.building,
                floor=d.location.floor,
                rack_id=d.location.rack_id,
                rack_unit=d.location.rack_unit,
            ),
            parent_id=d.parent_id,
            ip_addresses=d.ip_addresses,
            vlan_ids=d.vlan_ids,
            metrics=MetricsOut(
                cpu_utilization=d.metrics.cpu_utilization,
                memory_utilization=d.metrics.memory_utilization,
                uptime_hours=d.metrics.uptime_hours,
                client_count=d.metrics.client_count,
                interface_utilization=d.metrics.interface_utilization,
                packets_per_second=d.metrics.packets_per_second,
                error_rate=d.metrics.error_rate,
            ),
            active_failure_modes=d.active_failure_modes,
            failure_count_24h=d.failure_count_24h,
            last_failure_at=d.last_failure_at,
            api_protocol=d.sku.api.protocol.value,
            is_manually_failed=d.is_manually_failed,
            is_consumer_grade=d.sku.is_consumer_grade,
            children_ids=d.children_ids,
            available_failure_modes=[
                {
                    "id": fm_id,
                    "name": FAILURE_MODES[fm_id].name,
                    "severity": FAILURE_MODES[fm_id].severity,
                    "description": FAILURE_MODES[fm_id].description,
                }
                for fm_id in d.sku.failure_mode_ids
                if fm_id in FAILURE_MODES
            ],
        )


class SiteOut(BaseModel):
    id: str
    name: str
    site_type: str
    city: str
    state_code: str
    employee_count: int
    device_ids: list[str]
    device_count: int
    healthy_count: int
    impaired_count: int


class AlertOut(BaseModel):
    id: str
    timestamp: datetime
    sim_time: datetime
    event_type: str
    device_id: str
    hostname: str
    vendor: str
    site_name: str
    failure_mode_id: Optional[str] = None
    severity: str
    message: str
    is_manual: bool
    cascade_from_device_id: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None


class WorldSummaryOut(BaseModel):
    id: str
    seed: int
    org_name: str
    sim_time: datetime
    sim_speed: float
    is_running: bool
    total_devices: int
    healthy_count: int
    degraded_count: int
    failed_count: int
    unreachable_count: int
    rebooting_count: int
    total_sites: int
    active_alerts: int
    global_failure_multiplier: float
    tick_count: int


class TopologyNode(BaseModel):
    id: str
    label: str
    category: str
    state: str
    vendor: str
    site_id: str
    site_name: str
    parent_id: Optional[str] = None
    is_consumer_grade: bool = False


class TopologyEdge(BaseModel):
    source: str
    target: str
    link_type: str = "ethernet"


class TopologyOut(BaseModel):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]


class ChaosInjectRequest(BaseModel):
    device_id: str
    failure_mode_id: str


class ChaosPatternRequest(BaseModel):
    pattern: str   # "thundering_herd" | "rack_outage" | "wan_flap" | "bad_firmware" | "rolling_reboot"
    site_id: Optional[str] = None
    target_vendor: Optional[str] = None


class SimControlRequest(BaseModel):
    action: str     # "play" | "pause" | "set_speed" | "reset"
    speed: Optional[float] = None


class RemedyActionResult(BaseModel):
    success: bool
    device_id: str
    action: str
    vendor: str
    api_protocol: str
    latency_ms: float
    response: dict[str, Any]
    error: Optional[str] = None
    vendor_quirk_triggered: Optional[str] = None
