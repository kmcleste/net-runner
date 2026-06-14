"""
World generator and simulation tick engine.

World generation is seed-based: same seed + same org profile = same world.
The tick loop evaluates probabilistic failures, propagates cascades, and
broadcasts state changes via the event bus.
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import uuid
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from net_runner.catalog import (
    DEVICE_SKUS,
    FAILURE_MODES,
    DeviceCategory,
    DeviceState,
)
from net_runner.models import (
    DeviceInstance,
    DeviceMetrics,
    Location,
    SimClock,
    SimEvent,
    Site,
    World,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Insurance org profile
# ---------------------------------------------------------------------------

INSURANCE_ORG = {
    "hq": [
        {"city": "Chicago", "state": "IL", "employees": 2500, "buildings": 2, "floors": 8},
    ],
    "regional": [
        {"city": "New York", "state": "NY", "employees": 1800, "buildings": 1, "floors": 12},
        {"city": "Dallas", "state": "TX", "employees": 1500, "buildings": 1, "floors": 6},
        {"city": "Atlanta", "state": "GA", "employees": 1200, "buildings": 1, "floors": 5},
    ],
    "branch": [
        {"city": "Phoenix", "state": "AZ", "employees": 180},
        {"city": "Denver", "state": "CO", "employees": 150},
        {"city": "Seattle", "state": "WA", "employees": 160},
        {"city": "Boston", "state": "MA", "employees": 200},
        {"city": "Miami", "state": "FL", "employees": 120},
        {"city": "Minneapolis", "state": "MN", "employees": 100},
        {"city": "Detroit", "state": "MI", "employees": 90},
        {"city": "Kansas City", "state": "MO", "employees": 80},
        {"city": "Nashville", "state": "TN", "employees": 75},
        {"city": "Portland", "state": "OR", "employees": 70},
        {"city": "Salt Lake City", "state": "UT", "employees": 65},
        {"city": "Omaha", "state": "NE", "employees": 55},
        {"city": "Richmond", "state": "VA", "employees": 50},
        {"city": "Louisville", "state": "KY", "employees": 45},
        {"city": "Albuquerque", "state": "NM", "employees": 40},
    ],
}

# Device mix per site type — (sku_id, count_formula) where count_formula is a
# lambda taking (employee_count,) and returning number of devices to place
SITE_DEVICE_TEMPLATES: dict[str, list[dict]] = {
    "hq": [
        # Core / datacenter layer
        {"sku": "cisco_nexus9300_48x", "count": lambda e: 2, "role": "core"},
        {"sku": "cisco_asr1001x", "count": lambda e: 2, "role": "wan_edge"},
        {"sku": "palo_pa3220", "count": lambda e: 2, "role": "firewall_pair"},
        # Distribution
        {"sku": "cisco_cat9500_40x", "count": lambda e: max(2, e // 1000), "role": "distribution"},
        {"sku": "aruba_cx8400_32y", "count": lambda e: max(1, e // 1500), "role": "distribution"},
        # Access — mixed Cisco + Aruba
        {"sku": "cisco_cat9300_48p", "count": lambda e: max(4, e // 60), "role": "access"},
        {"sku": "aruba_cx6300_48g", "count": lambda e: max(2, e // 100), "role": "access"},
        # WAPs — mixed Aruba + Cisco (not Meraki at HQ)
        {"sku": "aruba_ap515", "count": lambda e: max(8, e // 25), "role": "wap"},
        {"sku": "cisco_cat9120ax", "count": lambda e: max(4, e // 40), "role": "wap"},
        # Servers
        {"sku": "dell_r750", "count": lambda e: max(6, e // 200), "role": "server"},
        {"sku": "hpe_dl380_gen10", "count": lambda e: max(4, e // 300), "role": "server"},
        {"sku": "dell_r650", "count": lambda e: max(4, e // 250), "role": "server"},
    ],
    "regional": [
        {"sku": "cisco_cat9500_40x", "count": lambda e: 2, "role": "core"},
        {"sku": "cisco_asr1001x", "count": lambda e: 1, "role": "wan_edge"},
        {"sku": "palo_pa820", "count": lambda e: 2, "role": "firewall_pair"},
        {"sku": "cisco_cat9300_48p", "count": lambda e: max(3, e // 80), "role": "access"},
        {"sku": "juniper_ex2300_24p", "count": lambda e: max(2, e // 120), "role": "access"},
        {"sku": "aruba_ap515", "count": lambda e: max(6, e // 30), "role": "wap"},
        {"sku": "meraki_mr46", "count": lambda e: max(4, e // 40), "role": "wap"},
        {"sku": "dell_r750", "count": lambda e: max(2, e // 400), "role": "server"},
        {"sku": "hpe_dl360_gen10", "count": lambda e: max(2, e // 500), "role": "server"},
    ],
    "branch": [
        {"sku": "cisco_isr4331", "count": lambda e: 1, "role": "wan_edge"},
        {"sku": "fortinet_fg100f", "count": lambda e: 1, "role": "firewall"},
        {"sku": "cisco_cat9200_24p", "count": lambda e: max(1, e // 50), "role": "access"},
        # Branch offices often have some shadow IT from before IT standardized
        {"sku": "netgear_gs308", "count": lambda e: 1 if e < 100 else 0, "role": "shadow"},
        {"sku": "meraki_mr36", "count": lambda e: max(2, e // 35), "role": "wap"},
        {"sku": "aruba_ap505", "count": lambda e: max(1, e // 50), "role": "wap"},
    ],
}

# Vendor mix for shadow IT "contamination" — small branches sometimes added their own
SHADOW_IT_SKUS = ["netgear_gs308", "tplink_tl_sg108e", "ubiquiti_u6_pro"]


def _pick_firmware(sku_id: str, rng: random.Random) -> str:
    """Pick a realistic (not always latest) firmware for a device."""
    sku = DEVICE_SKUS[sku_id]
    versions = sku.firmware_versions
    if not versions:
        return "unknown"
    # 70% chance of latest, 20% one behind, 10% older — mirrors real patch lag
    weights = [10] * len(versions)
    weights[-1] = 70
    if len(versions) > 1:
        weights[-2] = 20
    return rng.choices(versions, weights=weights)[0]


def _pick_age(site_type: str, role: str, rng: random.Random) -> float:
    """Device age in years — older at branches, newer at HQ core."""
    if site_type == "hq" and role in ("core", "firewall_pair"):
        return rng.uniform(0.5, 3.0)
    elif site_type == "branch" or role == "shadow":
        return rng.uniform(3.0, 8.0)
    else:
        return rng.uniform(1.0, 5.0)


def _assign_ips(site_idx: int, device_idx: int, vlan: int) -> list[str]:
    # 10.site.vlan.device — simplified but plausible RFC1918
    return [f"10.{site_idx}.{vlan}.{(device_idx % 253) + 1}"]


def generate_world(seed: int, org_name: str = "Midwest Mutual Insurance") -> World:
    """Procedurally generate a complete IT infrastructure world from a seed."""
    rng = random.Random(seed)
    now = datetime.utcnow()

    world_id = str(uuid.uuid4())
    sites: dict[str, Site] = {}
    devices: dict[str, DeviceInstance] = {}
    root_device_ids: list[str] = []  # WAN edges — no parent

    site_idx = 0
    for site_type, site_configs in INSURANCE_ORG.items():
        for cfg in site_configs:
            site_id = str(uuid.uuid4())
            site_name = f"{cfg['city']} {'HQ' if site_type == 'hq' else site_type.title()}"
            buildings = cfg.get("buildings", 1)
            floors = cfg.get("floors", 3)
            employee_count = cfg["employees"]

            site = Site(
                id=site_id,
                name=site_name,
                site_type=site_type,
                city=cfg["city"],
                state_code=cfg["state"],
                employee_count=employee_count,
                buildings=buildings,
                floors_per_building=floors,
            )

            templates = SITE_DEVICE_TEMPLATES[site_type]
            device_stack: dict[str, list[str]] = {}   # role -> [device_ids]

            dev_seq = 0
            for template in templates:
                sku_id = template["sku"]
                count = template["count"](employee_count)
                role = template["role"]
                if count <= 0:
                    continue

                if sku_id not in DEVICE_SKUS:
                    continue

                sku = DEVICE_SKUS[sku_id]
                device_stack[role] = device_stack.get(role, [])

                for i in range(count):
                    dev_id = str(uuid.uuid4())
                    dev_seq += 1

                    # Pick location within site
                    building = f"Bldg-{chr(65 + (dev_seq % buildings))}"
                    floor_num = (dev_seq % floors) + 1
                    rack_id = f"R{floor_num:02d}-{(dev_seq % 8) + 1:02d}"

                    hostname_prefix = {
                        "wan_edge": "wan",
                        "core": "core-sw",
                        "distribution": "dist-sw",
                        "firewall": "fw",
                        "firewall_pair": "fw",
                        "access": "acc-sw",
                        "wap": "ap",
                        "server": "srv",
                        "shadow": "shadow",
                    }.get(role, "dev")

                    city_code = cfg["city"].split()[0][:3].lower()
                    hostname = f"{hostname_prefix}-{city_code}-{i+1:02d}"

                    # VLAN assignment by role
                    vlan = {"core": 1, "wan_edge": 1, "distribution": 10, "access": 20,
                            "firewall": 1, "firewall_pair": 1, "wap": 30, "server": 40,
                            "shadow": 20}.get(role, 99)

                    firmware = _pick_firmware(sku_id, rng)
                    age = _pick_age(site_type, role, rng)

                    # Stagger initial uptime so not all devices have same uptime
                    initial_uptime = rng.uniform(0, sku.mtbf_hours * 0.3)

                    dev = DeviceInstance(
                        id=dev_id,
                        sku_id=sku_id,
                        sku=sku,
                        hostname=hostname,
                        firmware_version=firmware,
                        age_years=age,
                        location=Location(
                            site_id=site_id,
                            site_name=site_name,
                            site_type=site_type,
                            building=building,
                            floor=floor_num,
                            rack_id=rack_id,
                            rack_unit=dev_seq % 42 + 1,
                        ),
                        ip_addresses=_assign_ips(site_idx, dev_seq, vlan),
                        vlan_ids=[vlan, 99],  # 99 = mgmt VLAN
                        metrics=DeviceMetrics(
                            uptime_hours=initial_uptime,
                            cpu_utilization=rng.uniform(5, 35),
                            memory_utilization=rng.uniform(20, 60),
                            client_count=rng.randint(5, sku.max_clients // 2) if sku.max_clients else None,
                        ),
                    )

                    devices[dev_id] = dev
                    site.device_ids.append(dev_id)
                    device_stack[role].append(dev_id)

                    if role in ("wan_edge",):
                        root_device_ids.append(dev_id)

            # Wire up parent-child topology within site
            _wire_topology(device_stack, devices, root_device_ids)

            sites[site_id] = site
            site_idx += 1

    clock = SimClock(
        wall_start=now,
        sim_start=now - timedelta(days=rng.randint(30, 180)),  # Start sim in the past
        speed_multiplier=60.0,  # Default: 1 minute of sim per real second
    )

    world = World(
        id=world_id,
        seed=seed,
        org_name=org_name,
        created_at=now,
        clock=clock,
        sites=sites,
        devices=devices,
        events=[],
        active_alerts=[],
    )

    logger.info(
        "Generated world seed=%d sites=%d devices=%d",
        seed, len(sites), len(devices),
    )
    return world


def _wire_topology(
    stack: dict[str, list[str]],
    devices: dict[str, DeviceInstance],
    root_ids: list[str],
) -> None:
    """Connect devices in a hierarchical tree: core → dist → access → WAPs."""
    role_order = ["core", "distribution", "access", "wap", "server"]

    def connect(parent_ids: list[str], child_ids: list[str]) -> None:
        if not parent_ids or not child_ids:
            return
        for i, child_id in enumerate(child_ids):
            parent_id = parent_ids[i % len(parent_ids)]
            devices[child_id].parent_id = parent_id
            if child_id not in devices[parent_id].children_ids:
                devices[parent_id].children_ids.append(child_id)

    # WAN edge → core
    wan = stack.get("wan_edge", [])
    core = stack.get("core", [])
    if wan and core:
        connect(wan, core)
        for w in wan:
            root_ids.append(w) if w not in root_ids else None

    # core / wan_edge → distribution
    dist = stack.get("distribution", [])
    parents = core or wan
    if dist and parents:
        connect(parents, dist)

    # distribution (or core) → access
    access = stack.get("access", [])
    dist_or_core = dist or core or wan
    if access and dist_or_core:
        connect(dist_or_core, access)

    # access → WAPs
    waps = stack.get("wap", [])
    if waps and access:
        connect(access, waps)

    # access/core → servers
    servers = stack.get("server", [])
    server_parents = core or dist or access
    if servers and server_parents:
        connect(server_parents, servers)

    # firewall / firewall_pair → core or wan_edge
    fw = stack.get("firewall", stack.get("firewall_pair", []))
    fw_parent = wan or core
    if fw and fw_parent:
        connect(fw_parent, fw)

    # shadow IT hangs off access switches
    shadow = stack.get("shadow", [])
    if shadow and access:
        connect(access, shadow)


# ---------------------------------------------------------------------------
# Simulation tick engine
# ---------------------------------------------------------------------------

class SimulationEngine:
    """Drives the simulation forward, evaluates failures, propagates cascades."""

    TICK_REAL_SECONDS = 0.5   # How often the engine ticks (wall time)

    def __init__(self, world: World) -> None:
        self.world = world
        self._event_handlers: list[Callable[[SimEvent], Any]] = []
        self._task: Optional[asyncio.Task] = None

    def on_event(self, handler: Callable[[SimEvent], Any]) -> None:
        self._event_handlers.append(handler)

    async def start(self) -> None:
        self.world.clock.is_running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self.world.clock.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        while True:
            await asyncio.sleep(self.TICK_REAL_SECONDS)
            if not self.world.clock.is_running:
                continue
            try:
                self._tick()
            except Exception:
                logger.exception("Sim tick error")

    def _tick(self) -> None:
        world = self.world
        sim_hours = world.clock.advance(self.TICK_REAL_SECONDS)
        world.tick_count += 1

        sim_now = world.clock.sim_now
        rng = random.Random(world.seed + world.tick_count)

        # Time-of-day load factor: simulate morning storm, EOD batch
        hour_of_day = sim_now.hour
        load_factor = self._time_load_factor(hour_of_day)

        # Evaluate each device for new failures
        newly_failed: list[DeviceInstance] = []
        for device in world.devices.values():
            if device.state in (DeviceState.MAINTENANCE, DeviceState.REBOOTING):
                # Advance recovery
                self._tick_recovery(device, sim_hours, sim_now, rng)
                continue
            if device.state == DeviceState.UNREACHABLE:
                continue   # Transitive — will clear when parent recovers

            # Update metrics with time-of-day variation
            self._update_metrics(device, load_factor, sim_hours, rng)

            # Evaluate failure probability
            failure = self._evaluate_failure(device, sim_hours, load_factor, rng)
            if failure:
                self._apply_failure(device, failure, sim_now, newly_failed)

        # Propagate cascades from newly failed devices
        for device in newly_failed:
            self._propagate_cascade(device, sim_now)

        # Probabilistic recoveries
        self._tick_recoveries(sim_hours, sim_now, rng)

        # Trim alert list to last 500
        if len(world.active_alerts) > 500:
            world.active_alerts = world.active_alerts[-500:]

    def _time_load_factor(self, hour: int) -> float:
        """Return a load multiplier (0.3–2.0) based on hour of business day."""
        # Morning login storm: 8–9am
        if 8 <= hour < 9:
            return 2.0
        # Business hours: 9–17
        elif 9 <= hour < 17:
            return 1.2
        # EOD batch jobs: 17–19
        elif 17 <= hour < 19:
            return 1.5
        # Overnight maintenance window: 22–6
        elif hour >= 22 or hour < 6:
            return 0.3
        else:
            return 0.8

    def _update_metrics(
        self,
        device: DeviceInstance,
        load_factor: float,
        sim_hours: float,
        rng: random.Random,
    ) -> None:
        m = device.metrics
        m.uptime_hours += sim_hours

        # Base CPU varies by category and load
        base_cpu = {
            DeviceCategory.SERVER: 35,
            DeviceCategory.FIREWALL: 25,
            DeviceCategory.SWITCH_CORE: 15,
            DeviceCategory.WAP: 30,
        }.get(device.category, 20)

        target_cpu = base_cpu * load_factor * rng.uniform(0.7, 1.3)
        if device.state == DeviceState.DEGRADED:
            target_cpu = min(95, target_cpu * 2.5)
        m.cpu_utilization = min(99.9, m.cpu_utilization * 0.7 + target_cpu * 0.3)

        # Memory drifts upward with uptime (leak simulation)
        leak_factor = 1.0
        for fm_id in device.active_failure_modes:
            fm = FAILURE_MODES.get(fm_id)
            if fm and fm.uptime_factor:
                # Memory leak modes cause creeping memory growth
                leak_factor += 0.001 * sim_hours

        target_mem = min(99.9, 40 * load_factor * leak_factor * rng.uniform(0.8, 1.2))
        m.memory_utilization = min(99.9, m.memory_utilization * 0.8 + target_mem * 0.2)

        if device.sku.max_clients and device.state == DeviceState.HEALTHY:
            target_clients = int(device.sku.max_clients * 0.3 * load_factor)
            m.client_count = max(0, int((m.client_count or 0) * 0.6 + target_clients * 0.4))

    def _evaluate_failure(
        self,
        device: DeviceInstance,
        sim_hours: float,
        load_factor: float,
        rng: random.Random,
    ) -> Optional[str]:
        """Returns failure_mode_id if a failure triggers, else None."""
        if not device.sku.failure_mode_ids:
            return None

        for fm_id in device.sku.failure_mode_ids:
            if fm_id in device.active_failure_modes:
                continue   # Already active
            fm = FAILURE_MODES.get(fm_id)
            if not fm:
                continue

            # Base probability per tick
            p = fm.base_prob_per_hour * sim_hours

            # Modifiers
            if fm.uptime_factor:
                uptime_multiplier = 1.0 + math.log1p(device.metrics.uptime_hours / 720) * 0.5
                p *= uptime_multiplier
            if fm.load_factor:
                p *= load_factor
            if fm.age_factor:
                p *= (1.0 + device.age_years * 0.15)
            if fm.specific_firmware and device.firmware_version not in fm.specific_firmware:
                continue  # This failure mode doesn't affect this firmware

            # Global + device-level multipliers
            p *= self.world.global_failure_multiplier
            p *= device.failure_prob_modifier

            if rng.random() < p:
                return fm_id

        return None

    def _apply_failure(
        self,
        device: DeviceInstance,
        failure_mode_id: str,
        sim_now: datetime,
        newly_failed: list[DeviceInstance],
    ) -> None:
        fm = FAILURE_MODES[failure_mode_id]
        prev_state = device.state
        device.state = DeviceState(fm.resulting_state)
        device.active_failure_modes.append(failure_mode_id)
        device.last_failure_at = sim_now
        device.last_state_change = sim_now
        device.failure_count_24h += 1

        msg = (
            f"{device.hostname} [{device.vendor} {device.model}] "
            f"→ {fm.name}: {fm.description}"
        )
        event = self._make_event(
            device=device,
            event_type="failure",
            failure_mode_id=failure_mode_id,
            severity=fm.severity,
            message=msg,
            sim_now=sim_now,
            previous_state=prev_state.value,
            new_state=device.state.value,
        )
        self._emit(event)

        if device.state in (DeviceState.FAILED, DeviceState.REBOOTING):
            newly_failed.append(device)

    def _propagate_cascade(self, device: DeviceInstance, sim_now: datetime) -> None:
        """Mark downstream devices as UNREACHABLE when a parent fails."""
        def _cascade(dev_id: str, depth: int) -> None:
            if depth > 10:
                return
            dev = self.world.devices.get(dev_id)
            if not dev:
                return
            for child_id in dev.children_ids:
                child = self.world.devices.get(child_id)
                if not child or child.state == DeviceState.UNREACHABLE:
                    continue
                prev = child.state
                child.state = DeviceState.UNREACHABLE
                child.last_state_change = sim_now
                msg = (
                    f"{child.hostname} unreachable — parent {dev.hostname} "
                    f"({dev.vendor} {dev.model}) is {dev.state.value}"
                )
                event = self._make_event(
                    device=child,
                    event_type="cascade",
                    failure_mode_id=None,
                    severity="high",
                    message=msg,
                    sim_now=sim_now,
                    cascade_from_device_id=dev_id,
                    previous_state=prev.value,
                    new_state=DeviceState.UNREACHABLE.value,
                )
                self._emit(event)
                _cascade(child_id, depth + 1)

        _cascade(device.id, 0)

    def _tick_recovery(
        self,
        device: DeviceInstance,
        sim_hours: float,
        sim_now: datetime,
        rng: random.Random,
    ) -> None:
        """Advance rebooting/recovering devices toward healthy."""
        if not device.active_failure_modes:
            device.state = DeviceState.HEALTHY
            device.last_state_change = sim_now
            return

        # Check each active failure mode for recovery
        recovered_modes = []
        for fm_id in list(device.active_failure_modes):
            fm = FAILURE_MODES.get(fm_id)
            if not fm:
                recovered_modes.append(fm_id)
                continue
            mttr_min, mttr_max = fm.mttr_hours_range
            # Per-tick recovery probability
            avg_mttr = (mttr_min + mttr_max) / 2
            p_recover = sim_hours / avg_mttr if avg_mttr > 0 else 1.0
            if rng.random() < p_recover:
                recovered_modes.append(fm_id)

        for fm_id in recovered_modes:
            device.active_failure_modes.remove(fm_id)

        if not device.active_failure_modes:
            prev = device.state
            device.state = DeviceState.HEALTHY
            device.is_manually_failed = False
            device.last_state_change = sim_now
            device.metrics.uptime_hours = 0.0  # Reset uptime after reboot

            msg = f"{device.hostname} [{device.vendor} {device.model}] recovered → healthy"
            event = self._make_event(
                device=device,
                event_type="recovery",
                failure_mode_id=None,
                severity="low",
                message=msg,
                sim_now=sim_now,
                previous_state=prev.value,
                new_state=DeviceState.HEALTHY.value,
            )
            self._emit(event)

            # Clear UNREACHABLE children that were waiting on this device
            self._clear_cascade(device.id, sim_now)

    def _tick_recoveries(self, sim_hours: float, sim_now: datetime, rng: random.Random) -> None:
        for device in self.world.devices.values():
            if device.state in (DeviceState.REBOOTING, DeviceState.RECOVERING):
                self._tick_recovery(device, sim_hours, sim_now, rng)

    def _clear_cascade(self, recovered_parent_id: str, sim_now: datetime) -> None:
        """When a parent recovers, re-evaluate downstream UNREACHABLE devices."""
        parent = self.world.devices.get(recovered_parent_id)
        if not parent:
            return
        for child_id in parent.children_ids:
            child = self.world.devices.get(child_id)
            if child and child.state == DeviceState.UNREACHABLE:
                child.state = DeviceState.HEALTHY
                child.last_state_change = sim_now
                self._clear_cascade(child_id, sim_now)

    def _make_event(
        self,
        device: DeviceInstance,
        event_type: str,
        failure_mode_id: Optional[str],
        severity: str,
        message: str,
        sim_now: datetime,
        is_manual: bool = False,
        cascade_from_device_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
    ) -> SimEvent:
        event = SimEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            sim_time=sim_now,
            event_type=event_type,
            device_id=device.id,
            hostname=device.hostname,
            vendor=device.vendor,
            site_name=device.location.site_name,
            failure_mode_id=failure_mode_id,
            severity=severity,
            message=message,
            is_manual=is_manual,
            cascade_from_device_id=cascade_from_device_id,
            previous_state=previous_state,
            new_state=new_state,
        )
        self.world.events.append(event)
        if severity in ("high", "critical") or event_type in ("failure", "cascade"):
            self.world.active_alerts.append(event)
        return event

    def _emit(self, event: SimEvent) -> None:
        for handler in self._event_handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception:
                logger.exception("Event handler error")

    # ---------------------------------------------------------------------------
    # Manual chaos injection
    # ---------------------------------------------------------------------------

    def inject_failure(self, device_id: str, failure_mode_id: str) -> SimEvent:
        device = self.world.devices[device_id]
        fm = FAILURE_MODES[failure_mode_id]
        sim_now = self.world.clock.sim_now

        prev_state = device.state
        device.state = DeviceState(fm.resulting_state)
        device.active_failure_modes.append(failure_mode_id)
        device.last_failure_at = sim_now
        device.last_state_change = sim_now
        device.failure_count_24h += 1
        device.is_manually_failed = True

        msg = f"[MANUAL] {device.hostname} — {fm.name}: {fm.description}"
        event = self._make_event(
            device=device,
            event_type="manual_injection",
            failure_mode_id=failure_mode_id,
            severity=fm.severity,
            message=msg,
            sim_now=sim_now,
            is_manual=True,
            previous_state=prev_state.value,
            new_state=device.state.value,
        )
        self._emit(event)

        if device.state in (DeviceState.FAILED, DeviceState.REBOOTING):
            self._propagate_cascade(device, sim_now)

        return event

    def trigger_pattern(
        self,
        pattern: str,
        site_id: Optional[str] = None,
        target_vendor: Optional[str] = None,
    ) -> list[SimEvent]:
        """Trigger a named chaos pattern."""
        sim_now = self.world.clock.sim_now
        events: list[SimEvent] = []

        if pattern == "thundering_herd":
            events.extend(self._pattern_thundering_herd(sim_now))
        elif pattern == "rack_outage":
            events.extend(self._pattern_rack_outage(sim_now, site_id))
        elif pattern == "wan_flap":
            events.extend(self._pattern_wan_flap(sim_now, site_id))
        elif pattern == "bad_firmware":
            events.extend(self._pattern_bad_firmware(sim_now, target_vendor))
        elif pattern == "rolling_reboot":
            events.extend(self._pattern_rolling_reboot(sim_now, site_id))

        return events

    def _pattern_thundering_herd(self, sim_now: datetime) -> list[SimEvent]:
        """Simulate morning login storm hitting auth/core infrastructure."""
        events = []
        # Hit all core switches with load spike → increase failure probability
        for device in self.world.devices.values():
            if device.category in (DeviceCategory.SWITCH_CORE, DeviceCategory.SERVER):
                device.failure_prob_modifier = 5.0
                device.metrics.cpu_utilization = min(99.9, device.metrics.cpu_utilization * 2.5)
        # Trigger dhcp_scope_exhaustion on some WAPs
        for device in list(self.world.devices.values()):
            if device.category == DeviceCategory.WAP and "dhcp_scope_exhaustion" in device.sku.failure_mode_ids:
                events.append(self.inject_failure(device.id, "dhcp_scope_exhaustion"))
                if len(events) >= 5:
                    break
        return events

    def _pattern_rack_outage(self, sim_now: datetime, site_id: Optional[str]) -> list[SimEvent]:
        """Kill a PDU — takes out everything in a rack."""
        events = []
        candidates = [
            d for d in self.world.devices.values()
            if d.category == DeviceCategory.SWITCH_ACCESS
            and (site_id is None or d.location.site_id == site_id)
        ]
        if candidates:
            rng = random.Random(int(sim_now.timestamp()))
            victim = rng.choice(candidates)
            events.append(self.inject_failure(victim.id, "psu_failure"))
        return events

    def _pattern_wan_flap(self, sim_now: datetime, site_id: Optional[str]) -> list[SimEvent]:
        events = []
        wan_devices = [
            d for d in self.world.devices.values()
            if d.category == DeviceCategory.WAN_EDGE
            and (site_id is None or d.location.site_id == site_id)
        ]
        for dev in wan_devices[:2]:
            events.append(self.inject_failure(dev.id, "wan_interface_flap"))
        return events

    def _pattern_bad_firmware(self, sim_now: datetime, vendor: Optional[str]) -> list[SimEvent]:
        """Simulate a botched firmware push to a vendor's WAPs."""
        events = []
        targets = [
            d for d in self.world.devices.values()
            if d.category == DeviceCategory.WAP
            and (vendor is None or d.vendor.lower() == vendor.lower())
            and "bad_firmware_ota" in d.sku.failure_mode_ids
        ]
        rng = random.Random(int(sim_now.timestamp()))
        for dev in rng.sample(targets, min(len(targets), 8)):
            events.append(self.inject_failure(dev.id, "bad_firmware_ota"))
        return events

    def _pattern_rolling_reboot(self, sim_now: datetime, site_id: Optional[str]) -> list[SimEvent]:
        """Rolling reboot storm — devices spontaneously reboot across a site."""
        events = []
        candidates = [
            d for d in self.world.devices.values()
            if d.category in (DeviceCategory.SWITCH_ACCESS, DeviceCategory.WAP)
            and (site_id is None or d.location.site_id == site_id)
            and d.state == DeviceState.HEALTHY
        ]
        rng = random.Random(int(sim_now.timestamp()))
        for dev in rng.sample(candidates, min(len(candidates), 10)):
            events.append(self.inject_failure(dev.id, "memory_leak_ios"
                          if dev.category == DeviceCategory.SWITCH_ACCESS else "memory_leak_arubaos_8_6"))
        return events

    def reboot_device(self, device_id: str) -> SimEvent:
        device = self.world.devices[device_id]
        sim_now = self.world.clock.sim_now
        prev_state = device.state
        device.state = DeviceState.REBOOTING
        device.active_failure_modes.clear()
        device.last_state_change = sim_now
        device.metrics.uptime_hours = 0.0

        msg = f"[REBOOT] {device.hostname} [{device.vendor} {device.model}] initiated"
        return self._make_event(
            device=device,
            event_type="reboot",
            failure_mode_id=None,
            severity="medium",
            message=msg,
            sim_now=sim_now,
            is_manual=True,
            previous_state=prev_state.value,
            new_state=DeviceState.REBOOTING.value,
        )

    def set_maintenance(self, device_id: str, enable: bool) -> SimEvent:
        device = self.world.devices[device_id]
        sim_now = self.world.clock.sim_now
        prev_state = device.state
        device.state = DeviceState.MAINTENANCE if enable else DeviceState.HEALTHY
        device.last_state_change = sim_now

        msg = (f"[MAINTENANCE] {device.hostname} placed {'into' if enable else 'out of'} "
               f"maintenance mode")
        return self._make_event(
            device=device,
            event_type="maintenance",
            failure_mode_id=None,
            severity="low",
            message=msg,
            sim_now=sim_now,
            is_manual=True,
            previous_state=prev_state.value,
            new_state=device.state.value,
        )
