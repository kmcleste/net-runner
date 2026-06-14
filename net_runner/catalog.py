"""
Device catalog: vendors, SKUs, failure modes, and API characteristics.

Each vendor's API is a distinct integration surface — different protocol,
auth scheme, response schema, rate limits, and quirks. That friction is
intentional and is what makes vendor diversity painful (and interesting).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DeviceCategory(str, Enum):
    WAN_EDGE = "wan_edge"
    ROUTER = "router"
    SWITCH_CORE = "switch_core"
    SWITCH_DIST = "switch_dist"
    SWITCH_ACCESS = "switch_access"
    FIREWALL = "firewall"
    WAP = "wap"
    WIRELESS_CONTROLLER = "wireless_controller"
    LOAD_BALANCER = "load_balancer"
    SERVER = "server"
    STORAGE = "storage"
    ENDPOINT = "endpoint"
    PHONE = "phone"
    PRINTER = "printer"
    UPS = "ups"
    PDU = "pdu"


class DeviceState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"        # Partial failure; still passes traffic
    FAILED = "failed"            # Hard failure; no service
    UNREACHABLE = "unreachable"  # Transitive — parent is down
    RECOVERING = "recovering"    # Automated or manual remediation underway
    REBOOTING = "rebooting"      # Restart in progress
    MAINTENANCE = "maintenance"  # Admin-placed out of service


class APIProtocol(str, Enum):
    """Every value here is a distinct integration contract.
    An agent that handles Cisco IOS-XE cannot blindly reuse that handler for Meraki."""
    IOS_XE_RESTCONF = "ios_xe_restconf"       # YANG/RESTCONF, JSON
    NXOS_REST = "nxos_rest"                   # NX-API REST, JSON or XML
    MERAKI_DASHBOARD = "meraki_dashboard"      # Cloud REST, JSON, rate-limited, api-key
    ARUBA_CENTRAL = "aruba_central"           # Cloud REST, JWT token, JSON
    ARUBA_OS_CX = "aruba_os_cx"              # On-box REST, session cookie, JSON
    NETCONF_XML = "netconf_xml"              # RFC 6241, XML, SSH transport
    PAN_OS_XML = "pan_os_xml"               # Palo Alto XML API over HTTPS
    FORTI_OS_REST = "forti_os_rest"         # FortiOS REST, JSON, token
    DELL_REDFISH = "dell_redfish"           # DMTF Redfish, JSON
    HPE_REDFISH = "hpe_redfish"             # DMTF Redfish (iLO), JSON — schema differs from Dell
    SNMP_V2C = "snmp_v2c"                  # Read-only SNMP — community string, no auth
    SNMP_V3 = "snmp_v3"                    # SNMPv3 with auth+priv
    SSH_CLI = "ssh_cli"                     # Screen-scraping — no structured API
    NONE = "none"                           # Shadow IT: no management plane at all


class AuthMethod(str, Enum):
    BASIC = "basic"                  # HTTP Basic (username:password)
    TOKEN_BEARER = "token_bearer"    # Authorization: Bearer <token>
    API_KEY_HEADER = "api_key_header"  # X-Cisco-Meraki-API-Key or similar
    SESSION_COOKIE = "session_cookie"  # Login POST → session cookie
    SSH_KEY = "ssh_key"
    NONE = "none"


@dataclass
class APISpec:
    protocol: APIProtocol
    auth_method: AuthMethod
    avg_latency_ms: float
    latency_stddev_ms: float
    base_error_rate: float              # P(call fails) under normal load
    rate_limit_rps: Optional[float]     # None = no enforced limit
    cloud_dependent: bool = False       # Management plane routes through vendor cloud
    session_ttl_minutes: Optional[int] = None
    response_format: str = "json"       # "json" or "xml"
    quirks: list[str] = field(default_factory=list)


@dataclass
class FailureMode:
    id: str
    name: str
    description: str
    severity: str                           # "low" | "medium" | "high" | "critical"
    base_prob_per_hour: float               # Base P(trigger) per sim hour
    resulting_state: str                    # DeviceState value
    mttr_hours_range: tuple[float, float]   # (min, max) recovery time
    uptime_factor: bool = False             # P increases with device uptime
    load_factor: bool = False               # P increases when device is under load
    age_factor: bool = False                # P increases with device age
    specific_firmware: Optional[list[str]] = None  # None = affects all firmware
    cascades_downstream: bool = True
    affects_clients: bool = True
    vendor_specific_notes: str = ""


@dataclass
class DeviceSKU:
    vendor: str
    product_line: str
    model: str
    category: DeviceCategory
    # Physical specs
    port_count: Optional[int] = None
    max_clients: Optional[int] = None
    max_sessions: Optional[int] = None
    throughput_gbps: Optional[float] = None
    cpu_cores: Optional[int] = None
    ram_gb: Optional[int] = None
    storage_tb: Optional[float] = None
    power_watts: float = 0
    # Reliability
    mtbf_hours: float = 87600  # 10 years default
    end_of_support_year: Optional[int] = None
    is_consumer_grade: bool = False
    # API integration surface
    api: APISpec = field(default_factory=lambda: APISpec(
        protocol=APIProtocol.NONE,
        auth_method=AuthMethod.NONE,
        avg_latency_ms=0,
        latency_stddev_ms=0,
        base_error_rate=1.0,
        rate_limit_rps=None,
    ))
    # Failure mode IDs from FAILURE_MODES registry
    failure_mode_ids: list[str] = field(default_factory=list)
    firmware_versions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Failure mode library
# ---------------------------------------------------------------------------

FAILURE_MODES: dict[str, FailureMode] = {
    # --- Access / Distribution switches ---
    "memory_leak_ios": FailureMode(
        id="memory_leak_ios",
        name="IOS Memory Leak",
        description="Cisco IOS memory pool exhaustion; process crashes, device becomes unresponsive.",
        severity="high",
        base_prob_per_hour=0.00015,
        resulting_state=DeviceState.FAILED,
        mttr_hours_range=(0.25, 1.5),
        uptime_factor=True,   # much more likely after 90+ days uptime
        vendor_specific_notes="Fix requires reboot; no warm restart. IOS-XE < 17.6 most affected.",
    ),
    "stp_instability": FailureMode(
        id="stp_instability",
        name="STP Topology Change Storm",
        description="Rapid topology changes flood the network with TCN BPDUs, causing MAC table flushes.",
        severity="high",
        base_prob_per_hour=0.00008,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.1, 0.5),
        load_factor=True,
        cascades_downstream=True,
    ),
    "mac_table_overflow": FailureMode(
        id="mac_table_overflow",
        name="CAM Table Overflow",
        description="MAC address table full; switch floods all frames, saturating links.",
        severity="medium",
        base_prob_per_hour=0.00005,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.05, 0.25),
        load_factor=True,
        cascades_downstream=False,
    ),
    "stack_ring_break": FailureMode(
        id="stack_ring_break",
        name="StackWise Ring Break",
        description="Cisco StackWise ring fails; stack member enters half-ring mode with reduced bandwidth.",
        severity="high",
        base_prob_per_hour=0.00003,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.5, 4.0),
        age_factor=True,
        specific_firmware=None,
        vendor_specific_notes="Requires manual re-seating of stack cable or replacement. DNA Center shows stack errors.",
    ),
    "dnac_dependency_loss": FailureMode(
        id="dnac_dependency_loss",
        name="DNA Center Connectivity Loss",
        description="Device loses telemetry and policy sync with Cisco DNA Center; operates in degraded assurance mode.",
        severity="low",
        base_prob_per_hour=0.0002,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.1, 2.0),
        cascades_downstream=False,
        affects_clients=False,
        vendor_specific_notes="Data plane continues; control plane features like AI-driven QoS degrade.",
    ),
    "port_flap": FailureMode(
        id="port_flap",
        name="Interface Flapping",
        description="Physical layer instability causes repeated link-up/link-down events.",
        severity="medium",
        base_prob_per_hour=0.0001,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.5, 8.0),
        age_factor=True,
        load_factor=False,
    ),
    "psu_failure": FailureMode(
        id="psu_failure",
        name="Power Supply Failure",
        description="PSU failure; redundant units absorb load (degraded), single PSU causes outage.",
        severity="critical",
        base_prob_per_hour=0.000025,
        resulting_state=DeviceState.FAILED,
        mttr_hours_range=(2.0, 24.0),
        age_factor=True,
        cascades_downstream=True,
    ),
    "fan_failure_thermal": FailureMode(
        id="fan_failure_thermal",
        name="Fan Failure / Thermal Throttle",
        description="Fan module fails; CPU throttles to prevent damage, degrading throughput.",
        severity="medium",
        base_prob_per_hour=0.00004,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(1.0, 8.0),
        age_factor=True,
        cascades_downstream=False,
    ),
    "dhcp_relay_failure": FailureMode(
        id="dhcp_relay_failure",
        name="DHCP Relay Agent Failure",
        description="DHCP relay stops forwarding; new clients cannot obtain addresses.",
        severity="high",
        base_prob_per_hour=0.00006,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.1, 0.5),
        specific_firmware=None,
        affects_clients=True,
    ),
    # --- WAPs ---
    "client_association_storm": FailureMode(
        id="client_association_storm",
        name="Client Association Storm",
        description="Burst of simultaneous 802.11 associations overwhelms AP; CPU spikes, clients time out.",
        severity="medium",
        base_prob_per_hour=0.0003,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.05, 0.25),
        load_factor=True,
    ),
    "rf_interference": FailureMode(
        id="rf_interference",
        name="RF Interference / Channel Congestion",
        description="Non-Wi-Fi interference or neighbor AP density causes high retry rates and disconnects.",
        severity="medium",
        base_prob_per_hour=0.0002,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.25, 2.0),
        cascades_downstream=False,
    ),
    "dhcp_scope_exhaustion": FailureMode(
        id="dhcp_scope_exhaustion",
        name="DHCP Scope Exhaustion",
        description="Per-VLAN /25 or /26 subnet is full; new clients get APIPA addresses.",
        severity="high",
        base_prob_per_hour=0.00015,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.1, 1.0),
        load_factor=True,
        affects_clients=True,
    ),
    "memory_leak_arubaos_8_6": FailureMode(
        id="memory_leak_arubaos_8_6",
        name="ArubaOS 8.6 Memory Leak",
        description="ArubaOS 8.6.x kernel memory leak; AP crashes and reboots after ~14 days uptime.",
        severity="high",
        base_prob_per_hour=0.0003,
        resulting_state=DeviceState.REBOOTING,
        mttr_hours_range=(0.1, 0.2),
        uptime_factor=True,
        specific_firmware=["AOS-8.6.0.0", "AOS-8.6.0.4", "AOS-8.6.0.8"],
        vendor_specific_notes="Fixed in AOS-8.6.0.20. Aruba Central pushes auto-update but deployment can lag weeks.",
    ),
    "meraki_cloud_disconnect": FailureMode(
        id="meraki_cloud_disconnect",
        name="Meraki Cloud Management Loss",
        description="AP loses connection to Meraki dashboard cloud; management plane dark, data plane continues.",
        severity="medium",
        base_prob_per_hour=0.0001,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.05, 0.5),
        cascades_downstream=False,
        affects_clients=False,
        vendor_specific_notes="Clients stay connected but config changes, analytics, and alerts are blocked.",
    ),
    "meraki_license_expiry": FailureMode(
        id="meraki_license_expiry",
        name="Meraki License Expiry Hard Block",
        description="Enterprise license expires; Meraki hard-blocks device after 30-day grace period.",
        severity="critical",
        base_prob_per_hour=0.0,   # Triggered by sim time, not probability
        resulting_state=DeviceState.FAILED,
        mttr_hours_range=(1.0, 24.0),
        cascades_downstream=True,
        vendor_specific_notes="Recovery requires purchasing renewal and applying via dashboard API.",
    ),
    "captive_portal_crash": FailureMode(
        id="captive_portal_crash",
        name="Guest Captive Portal Crash",
        description="Captive portal service OOM; guest SSID stops authenticating new users.",
        severity="medium",
        base_prob_per_hour=0.0001,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.1, 0.5),
        uptime_factor=True,
        affects_clients=True,
    ),
    "bad_firmware_ota": FailureMode(
        id="bad_firmware_ota",
        name="Firmware OTA Failure",
        description="In-flight OTA firmware update corrupts flash; device stuck in boot loop.",
        severity="critical",
        base_prob_per_hour=0.00002,
        resulting_state=DeviceState.FAILED,
        mttr_hours_range=(1.0, 8.0),
        cascades_downstream=True,
    ),
    # --- Firewalls ---
    "session_table_exhaustion": FailureMode(
        id="session_table_exhaustion",
        name="Session Table Exhaustion",
        description="Max concurrent sessions reached; new flows are dropped. Typically triggered by DDoS or port scan.",
        severity="critical",
        base_prob_per_hour=0.00008,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.1, 1.0),
        load_factor=True,
        cascades_downstream=False,
    ),
    "ha_failover_delay": FailureMode(
        id="ha_failover_delay",
        name="HA Failover Gap",
        description="Active unit fails; passive takes 30-60s to assume active role. Connections reset during gap.",
        severity="high",
        base_prob_per_hour=0.00005,
        resulting_state=DeviceState.RECOVERING,
        mttr_hours_range=(0.008, 0.017),  # 30–60 seconds
        cascades_downstream=True,
    ),
    "content_update_loop": FailureMode(
        id="content_update_loop",
        name="PAN-OS Content Update Loop",
        description="Threat content update fails mid-install; device loops retrying, degrading performance.",
        severity="medium",
        base_prob_per_hour=0.00012,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.25, 2.0),
        specific_firmware=["PAN-OS 10.2.3", "PAN-OS 10.2.4"],
        vendor_specific_notes="PAN-OS XML API still responds; use op command to cancel install.",
    ),
    "ssl_inspection_cpu_spike": FailureMode(
        id="ssl_inspection_cpu_spike",
        name="SSL Inspection CPU Saturation",
        description="Decryption policy at capacity; firewall CPU hits 99%, latency spikes 10x.",
        severity="high",
        base_prob_per_hour=0.00010,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.1, 0.5),
        load_factor=True,
    ),
    "ips_signature_crash": FailureMode(
        id="ips_signature_crash",
        name="Fortinet IPS Signature Kernel Panic",
        description="Specific IPS signature database triggers a kernel panic on FortiOS 7.0.x.",
        severity="critical",
        base_prob_per_hour=0.00006,
        resulting_state=DeviceState.FAILED,
        mttr_hours_range=(0.25, 1.0),
        specific_firmware=["FortiOS 7.0.3", "FortiOS 7.0.4", "FortiOS 7.0.5"],
        vendor_specific_notes="TAC workaround: disable IPS engine before updating signatures. Fixed in 7.0.6.",
    ),
    "routing_table_corruption": FailureMode(
        id="routing_table_corruption",
        name="Routing Table Corruption",
        description="BGP/OSPF state corruption causes traffic blackholing on specific prefixes.",
        severity="critical",
        base_prob_per_hour=0.00004,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.25, 2.0),
        cascades_downstream=True,
    ),
    # --- WAN / Routers ---
    "bgp_session_drop": FailureMode(
        id="bgp_session_drop",
        name="BGP Peer Session Drop",
        description="MPLS provider BGP peer drops; site loses primary WAN path, fails over to secondary.",
        severity="high",
        base_prob_per_hour=0.00020,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.25, 4.0),
        cascades_downstream=False,
    ),
    "wan_interface_flap": FailureMode(
        id="wan_interface_flap",
        name="WAN Interface Flap",
        description="Physical or logical WAN interface oscillating up/down; triggers BGP reconvergence.",
        severity="high",
        base_prob_per_hour=0.00015,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.5, 12.0),
        age_factor=True,
        cascades_downstream=True,
    ),
    "nat_table_full": FailureMode(
        id="nat_table_full",
        name="NAT Translation Table Full",
        description="NAT table at capacity; outbound connections from branch fail silently.",
        severity="high",
        base_prob_per_hour=0.00008,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.1, 0.5),
        load_factor=True,
    ),
    # --- Servers ---
    "disk_failure_raid": FailureMode(
        id="disk_failure_raid",
        name="RAID Member Disk Failure",
        description="Drive failure degrades RAID array; performance reduced, data at risk until rebuild.",
        severity="high",
        base_prob_per_hour=0.00005,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(4.0, 48.0),
        age_factor=True,
        cascades_downstream=False,
    ),
    "memory_ecc_uncorrectable": FailureMode(
        id="memory_ecc_uncorrectable",
        name="Uncorrectable ECC Memory Error",
        description="DIMM failure causes kernel panic; server crashes and restarts.",
        severity="critical",
        base_prob_per_hour=0.000015,
        resulting_state=DeviceState.REBOOTING,
        mttr_hours_range=(0.1, 0.5),
        age_factor=True,
    ),
    "bmc_lockup": FailureMode(
        id="bmc_lockup",
        name="BMC / iDRAC Lockup",
        description="Baseboard Management Controller stops responding; out-of-band management lost.",
        severity="medium",
        base_prob_per_hour=0.00003,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.25, 2.0),
        uptime_factor=True,
        cascades_downstream=False,
        affects_clients=False,
        vendor_specific_notes="OS continues running; Redfish API unreachable until BMC reset.",
    ),
    "kernel_panic": FailureMode(
        id="kernel_panic",
        name="OS Kernel Panic",
        description="Server OS crashes; causes service outage and potentially cascades to dependent apps.",
        severity="critical",
        base_prob_per_hour=0.000012,
        resulting_state=DeviceState.REBOOTING,
        mttr_hours_range=(0.2, 1.0),
        load_factor=True,
        cascades_downstream=True,
    ),
    # --- Infrastructure shared ---
    "ups_battery_failure": FailureMode(
        id="ups_battery_failure",
        name="UPS Battery Failure",
        description="UPS battery depleted or failed; rack has no power backup during grid fluctuation.",
        severity="high",
        base_prob_per_hour=0.00002,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(2.0, 48.0),
        age_factor=True,
        cascades_downstream=False,
    ),
    "pdu_breaker_trip": FailureMode(
        id="pdu_breaker_trip",
        name="PDU Circuit Breaker Trip",
        description="Overloaded circuit trips breaker; entire PDU branch loses power.",
        severity="critical",
        base_prob_per_hour=0.000010,
        resulting_state=DeviceState.FAILED,
        mttr_hours_range=(0.5, 2.0),
        load_factor=True,
        cascades_downstream=True,
    ),
    # --- Shadow IT ---
    "consumer_reboot_loop": FailureMode(
        id="consumer_reboot_loop",
        name="Consumer Device Reboot Loop",
        description="Consumer-grade device enters reboot loop; requires physical power cycle.",
        severity="high",
        base_prob_per_hour=0.002,
        resulting_state=DeviceState.FAILED,
        mttr_hours_range=(0.25, 8.0),
        age_factor=True,
        uptime_factor=True,
        vendor_specific_notes="No remote management API. Requires physical intervention at branch.",
    ),
    "snmp_community_mismatch": FailureMode(
        id="snmp_community_mismatch",
        name="SNMP Community String Mismatch",
        description="SNMP community string rotated; monitoring loses visibility into device.",
        severity="low",
        base_prob_per_hour=0.0001,
        resulting_state=DeviceState.DEGRADED,
        mttr_hours_range=(0.25, 2.0),
        cascades_downstream=False,
        affects_clients=False,
    ),
}


# ---------------------------------------------------------------------------
# API specs per vendor
# ---------------------------------------------------------------------------

_CISCO_IOS_XE_API = APISpec(
    protocol=APIProtocol.IOS_XE_RESTCONF,
    auth_method=AuthMethod.BASIC,
    avg_latency_ms=180,
    latency_stddev_ms=60,
    base_error_rate=0.02,
    rate_limit_rps=None,
    response_format="json",
    quirks=[
        "YANG model path differs between IOS-XE 16.x and 17.x — version detection required",
        "RESTCONF returns 409 Conflict if a commit is in progress",
        "HTTP 200 on reboot trigger does not mean reboot succeeded — poll status separately",
    ],
)

_CISCO_NXOS_API = APISpec(
    protocol=APIProtocol.NXOS_REST,
    auth_method=AuthMethod.BASIC,
    avg_latency_ms=120,
    latency_stddev_ms=40,
    base_error_rate=0.015,
    rate_limit_rps=None,
    response_format="json",
    quirks=[
        "NX-API must be explicitly enabled: 'feature nxapi'",
        "VPC domain commands require sending to both peers",
        "JSON and XML modes are separate endpoints",
    ],
)

_MERAKI_API = APISpec(
    protocol=APIProtocol.MERAKI_DASHBOARD,
    auth_method=AuthMethod.API_KEY_HEADER,
    avg_latency_ms=350,
    latency_stddev_ms=180,
    base_error_rate=0.01,
    rate_limit_rps=5.0,  # 5 req/s per org — easy to hit during bulk ops
    cloud_dependent=True,
    response_format="json",
    quirks=[
        "Rate limit is per-organization, not per-API-key — shared across all callers",
        "Config changes asynchronous: API returns 200 but device may not apply for 30–90s",
        "Management plane goes dark if device loses internet; data plane continues independently",
        "Serial number required for device ops — not the MAC or hostname",
    ],
)

_ARUBA_CENTRAL_API = APISpec(
    protocol=APIProtocol.ARUBA_CENTRAL,
    auth_method=AuthMethod.TOKEN_BEARER,
    avg_latency_ms=280,
    latency_stddev_ms=100,
    base_error_rate=0.02,
    rate_limit_rps=10.0,
    cloud_dependent=True,
    session_ttl_minutes=120,
    response_format="json",
    quirks=[
        "Access token expires every 2h; refresh token expires every 14 days",
        "Group-based config model — can't push individual device config easily",
        "AP serial required (not MAC) for most device-level operations",
    ],
)

_ARUBA_OS_CX_API = APISpec(
    protocol=APIProtocol.ARUBA_OS_CX,
    auth_method=AuthMethod.SESSION_COOKIE,
    avg_latency_ms=220,
    latency_stddev_ms=70,
    base_error_rate=0.025,
    rate_limit_rps=None,
    session_ttl_minutes=30,
    response_format="json",
    quirks=[
        "Session cookie must be renewed before TTL — no refresh token mechanism",
        "Firmware upgrade via REST requires separate 'firmware-image' upload endpoint",
        "REST API versioned in URL path: /rest/v10.08/ — version pinning required",
    ],
)

_JUNIPER_NETCONF_API = APISpec(
    protocol=APIProtocol.NETCONF_XML,
    auth_method=AuthMethod.SSH_KEY,
    avg_latency_ms=550,
    latency_stddev_ms=150,
    base_error_rate=0.03,
    rate_limit_rps=None,
    response_format="xml",
    quirks=[
        "XML response; must parse YANG-conformant XML — no JSON option without Junos REST extension",
        "Candidate config lock required for edits; forgotten locks cause 'lock held' errors",
        "commit confirmed requires follow-up commit within timeout or auto-rollback occurs",
        "Errors returned as <rpc-error> inside a 200 OK — must always inspect body",
    ],
)

_PANOS_API = APISpec(
    protocol=APIProtocol.PAN_OS_XML,
    auth_method=AuthMethod.API_KEY_HEADER,
    avg_latency_ms=260,
    latency_stddev_ms=90,
    base_error_rate=0.015,
    rate_limit_rps=None,
    response_format="xml",
    quirks=[
        "API key generated via keygen endpoint; not the same as admin password",
        "All responses are XML including errors — client must parse regardless of success",
        "Two-phase commit: 'edit' then separate 'commit' job; poll job ID for result",
        "Panorama vs on-box API differ; target device serial must be specified for Panorama",
        "Operational commands via <type=op> are different from config commands",
    ],
)

_FORTIOS_API = APISpec(
    protocol=APIProtocol.FORTI_OS_REST,
    auth_method=AuthMethod.TOKEN_BEARER,
    avg_latency_ms=200,
    latency_stddev_ms=80,
    base_error_rate=0.02,
    rate_limit_rps=None,
    response_format="json",
    quirks=[
        "Token created per admin user — token scope matches admin VDOM access",
        "VDOM must be specified in URL or header for multi-VDOM systems",
        "Some resources still require CLI fallback — not fully RESTified",
        "Firmware upgrade API triggers instant reboot with no grace period",
    ],
)

_DELL_REDFISH_API = APISpec(
    protocol=APIProtocol.DELL_REDFISH,
    auth_method=AuthMethod.BASIC,
    avg_latency_ms=800,
    latency_stddev_ms=300,
    base_error_rate=0.04,
    rate_limit_rps=None,
    response_format="json",
    quirks=[
        "iDRAC response times are slow; default timeouts often fire — increase to 30s",
        "Dell extends Redfish with OEM properties under Oem.Dell — schema differs from HPE",
        "Job queue must be committed before config applies — two-phase like PAN-OS",
        "iDRAC lockup is not uncommon; Redfish becomes unresponsive while OS runs fine",
    ],
)

_HPE_REDFISH_API = APISpec(
    protocol=APIProtocol.HPE_REDFISH,
    auth_method=AuthMethod.SESSION_COOKIE,
    avg_latency_ms=600,
    latency_stddev_ms=250,
    base_error_rate=0.035,
    rate_limit_rps=None,
    session_ttl_minutes=30,
    response_format="json",
    quirks=[
        "iLO5 session limit is 20 concurrent sessions — exceeded sessions are rejected",
        "HPE OEM extensions under Oem.Hpe differ from Dell.Oem — not interchangeable",
        "Power actions (reboot) return a task resource; must poll task until complete",
        "iLO firmware separate from server firmware — both may need updates",
    ],
)

_SNMP_API = APISpec(
    protocol=APIProtocol.SNMP_V2C,
    auth_method=AuthMethod.NONE,
    avg_latency_ms=50,
    latency_stddev_ms=30,
    base_error_rate=0.05,
    rate_limit_rps=None,
    response_format="json",
    quirks=[
        "Read-only community string — no write capability without SNMPv3 + auth",
        "OID namespace varies by vendor MIB — must load vendor MIB before parsing",
        "SNMP traps are fire-and-forget UDP — missed traps mean missed alerts",
    ],
)

_NO_API = APISpec(
    protocol=APIProtocol.NONE,
    auth_method=AuthMethod.NONE,
    avg_latency_ms=0,
    latency_stddev_ms=0,
    base_error_rate=1.0,
    rate_limit_rps=None,
    quirks=["No management interface. Physical access only. SNMP not configured."],
)


# ---------------------------------------------------------------------------
# Device SKU catalog
# ---------------------------------------------------------------------------

DEVICE_SKUS: dict[str, DeviceSKU] = {

    # -----------------------------------------------------------------------
    # Cisco Systems — IOS-XE switches
    # -----------------------------------------------------------------------
    "cisco_cat9200_24p": DeviceSKU(
        vendor="Cisco",
        product_line="Catalyst 9200",
        model="C9200-24P",
        category=DeviceCategory.SWITCH_ACCESS,
        port_count=24,
        max_clients=120,
        throughput_gbps=0.128,
        power_watts=195,
        mtbf_hours=131400,  # ~15 years
        api=_CISCO_IOS_XE_API,
        failure_mode_ids=["memory_leak_ios", "stp_instability", "mac_table_overflow",
                          "port_flap", "psu_failure", "dhcp_relay_failure", "fan_failure_thermal"],
        firmware_versions=["17.3.1", "17.6.3", "17.9.1", "17.12.1"],
    ),
    "cisco_cat9300_48p": DeviceSKU(
        vendor="Cisco",
        product_line="Catalyst 9300",
        model="C9300-48P",
        category=DeviceCategory.SWITCH_ACCESS,
        port_count=48,
        max_clients=240,
        throughput_gbps=0.256,
        power_watts=390,
        mtbf_hours=131400,
        api=_CISCO_IOS_XE_API,
        failure_mode_ids=["memory_leak_ios", "stp_instability", "stack_ring_break",
                          "dnac_dependency_loss", "mac_table_overflow", "port_flap",
                          "psu_failure", "fan_failure_thermal"],
        firmware_versions=["17.6.3", "17.9.4", "17.12.1", "17.12.3"],
    ),
    "cisco_cat9500_40x": DeviceSKU(
        vendor="Cisco",
        product_line="Catalyst 9500",
        model="C9500-40X",
        category=DeviceCategory.SWITCH_DIST,
        port_count=40,
        throughput_gbps=3.2,
        power_watts=600,
        mtbf_hours=175200,
        api=_CISCO_IOS_XE_API,
        failure_mode_ids=["memory_leak_ios", "stp_instability", "routing_table_corruption",
                          "psu_failure", "fan_failure_thermal", "dnac_dependency_loss"],
        firmware_versions=["17.9.4", "17.12.1", "17.12.3"],
    ),
    "cisco_nexus9300_48x": DeviceSKU(
        vendor="Cisco",
        product_line="Nexus 9300",
        model="N9K-C93180YC-EX",
        category=DeviceCategory.SWITCH_CORE,
        port_count=48,
        throughput_gbps=6.4,
        power_watts=700,
        mtbf_hours=175200,
        api=_CISCO_NXOS_API,
        failure_mode_ids=["stp_instability", "routing_table_corruption", "psu_failure",
                          "fan_failure_thermal", "bgp_session_drop"],
        firmware_versions=["9.3.10", "10.2.5", "10.3.3"],
    ),

    # -----------------------------------------------------------------------
    # Cisco — Routers / WAN edge
    # -----------------------------------------------------------------------
    "cisco_asr1001x": DeviceSKU(
        vendor="Cisco",
        product_line="ASR 1000",
        model="ASR1001-X",
        category=DeviceCategory.WAN_EDGE,
        throughput_gbps=20.0,
        power_watts=400,
        mtbf_hours=175200,
        api=_CISCO_IOS_XE_API,
        failure_mode_ids=["bgp_session_drop", "wan_interface_flap", "routing_table_corruption",
                          "nat_table_full", "psu_failure", "fan_failure_thermal"],
        firmware_versions=["16.12.6", "17.6.3", "17.9.4"],
    ),
    "cisco_isr4331": DeviceSKU(
        vendor="Cisco",
        product_line="ISR 4000",
        model="ISR4331/K9",
        category=DeviceCategory.ROUTER,
        throughput_gbps=1.0,
        power_watts=150,
        mtbf_hours=131400,
        api=_CISCO_IOS_XE_API,
        failure_mode_ids=["bgp_session_drop", "wan_interface_flap", "nat_table_full",
                          "memory_leak_ios", "psu_failure"],
        firmware_versions=["16.12.6", "17.6.3", "17.9.4"],
    ),

    # -----------------------------------------------------------------------
    # Cisco — Wireless (IOS-XE based, not Meraki)
    # -----------------------------------------------------------------------
    "cisco_cat9120ax": DeviceSKU(
        vendor="Cisco",
        product_line="Catalyst 9100",
        model="C9120AX",
        category=DeviceCategory.WAP,
        max_clients=800,
        power_watts=25,
        mtbf_hours=87600,
        api=_CISCO_IOS_XE_API,
        failure_mode_ids=["client_association_storm", "rf_interference", "dhcp_scope_exhaustion",
                          "bad_firmware_ota", "captive_portal_crash"],
        firmware_versions=["17.9.1", "17.9.4", "17.12.1"],
    ),

    # -----------------------------------------------------------------------
    # Cisco Meraki — cloud-managed (DIFFERENT API from above Cisco gear!)
    # -----------------------------------------------------------------------
    "meraki_mr46": DeviceSKU(
        vendor="Cisco Meraki",
        product_line="MR",
        model="MR46",
        category=DeviceCategory.WAP,
        max_clients=500,
        power_watts=22,
        mtbf_hours=87600,
        api=_MERAKI_API,
        failure_mode_ids=["meraki_cloud_disconnect", "meraki_license_expiry",
                          "client_association_storm", "rf_interference", "dhcp_scope_exhaustion",
                          "bad_firmware_ota"],
        firmware_versions=["MR 29.5", "MR 30.7", "MR 31.0"],
    ),
    "meraki_mr36": DeviceSKU(
        vendor="Cisco Meraki",
        product_line="MR",
        model="MR36",
        category=DeviceCategory.WAP,
        max_clients=300,
        power_watts=15,
        mtbf_hours=87600,
        api=_MERAKI_API,
        failure_mode_ids=["meraki_cloud_disconnect", "meraki_license_expiry",
                          "client_association_storm", "rf_interference", "bad_firmware_ota"],
        firmware_versions=["MR 29.5", "MR 30.7", "MR 31.0"],
    ),
    "meraki_ms120_48": DeviceSKU(
        vendor="Cisco Meraki",
        product_line="MS",
        model="MS120-48",
        category=DeviceCategory.SWITCH_ACCESS,
        port_count=48,
        max_clients=240,
        power_watts=65,
        mtbf_hours=131400,
        api=_MERAKI_API,
        failure_mode_ids=["meraki_cloud_disconnect", "meraki_license_expiry", "stp_instability",
                          "psu_failure", "port_flap"],
        firmware_versions=["MS 14.31", "MS 14.33", "MS 15.21"],
    ),
    "meraki_mx85": DeviceSKU(
        vendor="Cisco Meraki",
        product_line="MX",
        model="MX85",
        category=DeviceCategory.FIREWALL,
        throughput_gbps=1.0,
        power_watts=60,
        mtbf_hours=131400,
        api=_MERAKI_API,
        failure_mode_ids=["meraki_cloud_disconnect", "meraki_license_expiry",
                          "session_table_exhaustion", "wan_interface_flap", "bgp_session_drop"],
        firmware_versions=["MX 18.107", "MX 18.211"],
    ),

    # -----------------------------------------------------------------------
    # Aruba / HPE — switches (ArubaOS-CX, on-box REST)
    # -----------------------------------------------------------------------
    "aruba_cx6300_48g": DeviceSKU(
        vendor="Aruba",
        product_line="CX 6300",
        model="JL659A",
        category=DeviceCategory.SWITCH_ACCESS,
        port_count=48,
        max_clients=240,
        throughput_gbps=0.176,
        power_watts=350,
        mtbf_hours=131400,
        api=_ARUBA_OS_CX_API,
        failure_mode_ids=["stp_instability", "mac_table_overflow", "psu_failure",
                          "port_flap", "dhcp_relay_failure", "fan_failure_thermal"],
        firmware_versions=["AOS-CX.10.09.1010", "AOS-CX.10.10.1030", "AOS-CX.10.11.0010"],
    ),
    "aruba_cx8400_32y": DeviceSKU(
        vendor="Aruba",
        product_line="CX 8400",
        model="JL679A",
        category=DeviceCategory.SWITCH_DIST,
        port_count=32,
        throughput_gbps=12.8,
        power_watts=900,
        mtbf_hours=175200,
        api=_ARUBA_OS_CX_API,
        failure_mode_ids=["stp_instability", "routing_table_corruption", "psu_failure",
                          "fan_failure_thermal"],
        firmware_versions=["AOS-CX.10.09.1010", "AOS-CX.10.10.1030"],
    ),

    # -----------------------------------------------------------------------
    # Aruba — WAPs (managed via Aruba Central cloud)
    # -----------------------------------------------------------------------
    "aruba_ap515": DeviceSKU(
        vendor="Aruba",
        product_line="AP-500 Series",
        model="AP-515",
        category=DeviceCategory.WAP,
        max_clients=1024,
        power_watts=25.5,
        mtbf_hours=87600,
        api=_ARUBA_CENTRAL_API,
        failure_mode_ids=["memory_leak_arubaos_8_6", "client_association_storm", "rf_interference",
                          "dhcp_scope_exhaustion", "bad_firmware_ota", "captive_portal_crash"],
        firmware_versions=["AOS-8.6.0.4", "AOS-8.6.0.20", "AOS-8.10.0.6", "AOS-8.11.0.0"],
    ),
    "aruba_ap505": DeviceSKU(
        vendor="Aruba",
        product_line="AP-500 Series",
        model="AP-505",
        category=DeviceCategory.WAP,
        max_clients=512,
        power_watts=15.4,
        mtbf_hours=87600,
        api=_ARUBA_CENTRAL_API,
        failure_mode_ids=["memory_leak_arubaos_8_6", "client_association_storm", "rf_interference",
                          "dhcp_scope_exhaustion", "bad_firmware_ota"],
        firmware_versions=["AOS-8.6.0.8", "AOS-8.6.0.20", "AOS-8.10.0.6"],
    ),

    # -----------------------------------------------------------------------
    # Juniper Networks — NETCONF/XML (the XML nightmare)
    # -----------------------------------------------------------------------
    "juniper_ex2300_24p": DeviceSKU(
        vendor="Juniper",
        product_line="EX2300",
        model="EX2300-24P",
        category=DeviceCategory.SWITCH_ACCESS,
        port_count=24,
        max_clients=120,
        throughput_gbps=0.128,
        power_watts=200,
        mtbf_hours=131400,
        api=_JUNIPER_NETCONF_API,
        failure_mode_ids=["stp_instability", "mac_table_overflow", "psu_failure",
                          "port_flap", "dhcp_relay_failure", "memory_leak_ios"],
        firmware_versions=["20.4R3", "21.4R3", "22.4R2", "23.4R1"],
    ),
    "juniper_ex4400_48p": DeviceSKU(
        vendor="Juniper",
        product_line="EX4400",
        model="EX4400-48P",
        category=DeviceCategory.SWITCH_DIST,
        port_count=48,
        throughput_gbps=1.44,
        power_watts=650,
        mtbf_hours=175200,
        api=_JUNIPER_NETCONF_API,
        failure_mode_ids=["stp_instability", "routing_table_corruption", "psu_failure",
                          "fan_failure_thermal", "bgp_session_drop"],
        firmware_versions=["21.4R3", "22.4R2", "23.2R1"],
    ),
    "juniper_srx300": DeviceSKU(
        vendor="Juniper",
        product_line="SRX300",
        model="SRX300",
        category=DeviceCategory.FIREWALL,
        throughput_gbps=1.0,
        power_watts=30,
        mtbf_hours=131400,
        api=_JUNIPER_NETCONF_API,
        failure_mode_ids=["session_table_exhaustion", "routing_table_corruption",
                          "wan_interface_flap", "psu_failure"],
        firmware_versions=["21.4R3", "22.4R2", "23.2R1"],
    ),

    # -----------------------------------------------------------------------
    # Palo Alto Networks — XML API (PAN-OS)
    # -----------------------------------------------------------------------
    "palo_pa3220": DeviceSKU(
        vendor="Palo Alto",
        product_line="PA-3000 Series",
        model="PA-3220",
        category=DeviceCategory.FIREWALL,
        max_sessions=1000000,
        throughput_gbps=5.0,
        power_watts=250,
        mtbf_hours=131400,
        api=_PANOS_API,
        failure_mode_ids=["session_table_exhaustion", "ha_failover_delay", "content_update_loop",
                          "ssl_inspection_cpu_spike", "routing_table_corruption", "psu_failure"],
        firmware_versions=["10.1.6", "10.2.3", "10.2.7", "11.0.2", "11.1.0"],
    ),
    "palo_pa820": DeviceSKU(
        vendor="Palo Alto",
        product_line="PA-800 Series",
        model="PA-820",
        category=DeviceCategory.FIREWALL,
        max_sessions=256000,
        throughput_gbps=1.0,
        power_watts=120,
        mtbf_hours=131400,
        api=_PANOS_API,
        failure_mode_ids=["session_table_exhaustion", "ha_failover_delay", "content_update_loop",
                          "ssl_inspection_cpu_spike", "psu_failure"],
        firmware_versions=["10.1.6", "10.2.3", "10.2.7", "11.0.2"],
    ),

    # -----------------------------------------------------------------------
    # Fortinet — FortiOS REST
    # -----------------------------------------------------------------------
    "fortinet_fg100f": DeviceSKU(
        vendor="Fortinet",
        product_line="FortiGate",
        model="FG-100F",
        category=DeviceCategory.FIREWALL,
        max_sessions=2000000,
        throughput_gbps=10.0,
        power_watts=75,
        mtbf_hours=131400,
        api=_FORTIOS_API,
        failure_mode_ids=["ips_signature_crash", "ssl_inspection_cpu_spike",
                          "session_table_exhaustion", "ha_failover_delay",
                          "routing_table_corruption", "psu_failure"],
        firmware_versions=["FortiOS 7.0.3", "FortiOS 7.0.5", "FortiOS 7.0.6",
                           "FortiOS 7.2.4", "FortiOS 7.4.0"],
    ),
    "fortinet_fg600f": DeviceSKU(
        vendor="Fortinet",
        product_line="FortiGate",
        model="FG-600F",
        category=DeviceCategory.FIREWALL,
        max_sessions=8000000,
        throughput_gbps=40.0,
        power_watts=220,
        mtbf_hours=175200,
        api=_FORTIOS_API,
        failure_mode_ids=["ips_signature_crash", "ssl_inspection_cpu_spike",
                          "session_table_exhaustion", "ha_failover_delay", "psu_failure"],
        firmware_versions=["FortiOS 7.0.5", "FortiOS 7.0.6", "FortiOS 7.2.4", "FortiOS 7.4.0"],
    ),

    # -----------------------------------------------------------------------
    # Dell — servers (Redfish via iDRAC)
    # -----------------------------------------------------------------------
    "dell_r750": DeviceSKU(
        vendor="Dell",
        product_line="PowerEdge",
        model="R750",
        category=DeviceCategory.SERVER,
        cpu_cores=64,
        ram_gb=512,
        storage_tb=9.6,
        power_watts=800,
        mtbf_hours=131400,
        api=_DELL_REDFISH_API,
        failure_mode_ids=["disk_failure_raid", "memory_ecc_uncorrectable", "bmc_lockup",
                          "kernel_panic", "psu_failure", "fan_failure_thermal"],
        firmware_versions=["iDRAC 7.00.30", "iDRAC 7.10.10"],
    ),
    "dell_r650": DeviceSKU(
        vendor="Dell",
        product_line="PowerEdge",
        model="R650",
        category=DeviceCategory.SERVER,
        cpu_cores=32,
        ram_gb=256,
        storage_tb=4.8,
        power_watts=550,
        mtbf_hours=131400,
        api=_DELL_REDFISH_API,
        failure_mode_ids=["disk_failure_raid", "memory_ecc_uncorrectable", "bmc_lockup",
                          "kernel_panic", "psu_failure", "fan_failure_thermal"],
        firmware_versions=["iDRAC 7.00.30", "iDRAC 7.10.10"],
    ),

    # -----------------------------------------------------------------------
    # HPE — servers (Redfish via iLO — same protocol, different OEM schema!)
    # -----------------------------------------------------------------------
    "hpe_dl380_gen10": DeviceSKU(
        vendor="HPE",
        product_line="ProLiant",
        model="DL380 Gen10",
        category=DeviceCategory.SERVER,
        cpu_cores=56,
        ram_gb=384,
        storage_tb=7.2,
        power_watts=800,
        mtbf_hours=131400,
        api=_HPE_REDFISH_API,
        failure_mode_ids=["disk_failure_raid", "memory_ecc_uncorrectable", "bmc_lockup",
                          "kernel_panic", "psu_failure", "fan_failure_thermal"],
        firmware_versions=["iLO5 2.72", "iLO5 3.00"],
    ),
    "hpe_dl360_gen10": DeviceSKU(
        vendor="HPE",
        product_line="ProLiant",
        model="DL360 Gen10",
        category=DeviceCategory.SERVER,
        cpu_cores=40,
        ram_gb=256,
        storage_tb=3.2,
        power_watts=500,
        mtbf_hours=131400,
        api=_HPE_REDFISH_API,
        failure_mode_ids=["disk_failure_raid", "memory_ecc_uncorrectable", "bmc_lockup",
                          "kernel_panic", "psu_failure"],
        firmware_versions=["iLO5 2.72", "iLO5 3.00"],
    ),

    # -----------------------------------------------------------------------
    # Shadow IT / Consumer grade — the nightmare at branch offices
    # -----------------------------------------------------------------------
    "netgear_gs308": DeviceSKU(
        vendor="Netgear",
        product_line="ProSAFE",
        model="GS308",
        category=DeviceCategory.SWITCH_ACCESS,
        port_count=8,
        max_clients=40,
        power_watts=5,
        mtbf_hours=35040,  # ~4 years — consumer grade
        is_consumer_grade=True,
        api=_NO_API,  # ZERO management interface
        failure_mode_ids=["consumer_reboot_loop", "psu_failure", "port_flap", "mac_table_overflow"],
        firmware_versions=["V2.0.0.4"],
    ),
    "tplink_tl_sg108e": DeviceSKU(
        vendor="TP-Link",
        product_line="Easy Smart",
        model="TL-SG108E",
        category=DeviceCategory.SWITCH_ACCESS,
        port_count=8,
        max_clients=40,
        power_watts=5,
        mtbf_hours=26280,  # ~3 years
        is_consumer_grade=True,
        api=APISpec(  # "Web GUI only" — effectively no programmatic API
            protocol=APIProtocol.SSH_CLI,
            auth_method=AuthMethod.BASIC,
            avg_latency_ms=2000,
            latency_stddev_ms=1000,
            base_error_rate=0.25,
            rate_limit_rps=1.0,
            quirks=["Web-only management; CLI via telnet (plaintext)", "No REST API at all",
                    "Config backup is binary blob — not human-readable"],
        ),
        failure_mode_ids=["consumer_reboot_loop", "psu_failure", "port_flap"],
        firmware_versions=["20211208"],
    ),
    "ubiquiti_u6_pro": DeviceSKU(
        vendor="Ubiquiti",
        product_line="UniFi",
        model="U6 Pro",
        category=DeviceCategory.WAP,
        max_clients=300,
        power_watts=19,
        mtbf_hours=52560,  # ~6 years
        is_consumer_grade=True,
        api=APISpec(
            protocol=APIProtocol.SSH_CLI,
            auth_method=AuthMethod.SESSION_COOKIE,
            avg_latency_ms=300,
            latency_stddev_ms=150,
            base_error_rate=0.08,
            rate_limit_rps=None,
            quirks=["UniFi controller must be running; device AP is dumb without it",
                    "Controller API undocumented/unofficial — breaks on UniFi OS updates",
                    "Local-only API: no cloud management option for enterprise use"],
        ),
        failure_mode_ids=["consumer_reboot_loop", "bad_firmware_ota", "client_association_storm",
                          "rf_interference", "snmp_community_mismatch"],
        firmware_versions=["6.2.14", "6.5.28", "7.0.35"],
    ),
}
