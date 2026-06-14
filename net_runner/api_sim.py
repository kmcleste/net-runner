"""
Vendor API simulation layer.

Each driver simulates the integration friction of a real vendor API:
latency, error rates, rate limiting, auth quirks, and vendor-specific
response schemas. This is where you build and test your remediation agents
before touching real devices.
"""

from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from net_runner.catalog import APIProtocol, DEVICE_SKUS, FAILURE_MODES
from net_runner.models import DeviceInstance, RemedyActionResult


class VendorAPIDriver(ABC):
    """Base class for all vendor API drivers."""

    protocol: APIProtocol

    async def call(
        self,
        device: DeviceInstance,
        action: str,
        payload: Optional[dict] = None,
    ) -> RemedyActionResult:
        start = time.monotonic()
        api = device.sku.api

        # Simulate network latency
        latency_ms = max(10.0, random.gauss(api.avg_latency_ms, api.latency_stddev_ms))
        await asyncio.sleep(latency_ms / 1000.0)

        # Rate limit simulation
        if api.rate_limit_rps is not None:
            await self._check_rate_limit(device, api.rate_limit_rps)

        # Cloud dependency failure
        if api.cloud_dependent and random.random() < 0.005:
            return RemedyActionResult(
                success=False,
                device_id=device.id,
                action=action,
                vendor=device.vendor,
                api_protocol=api.protocol.value,
                latency_ms=latency_ms,
                response={},
                error="Cloud management plane unreachable — check internet connectivity",
                vendor_quirk_triggered="cloud_management_loss",
            )

        # Base error rate (API call failure)
        if random.random() < api.base_error_rate:
            error_msg, quirk = self._vendor_error(device, action)
            return RemedyActionResult(
                success=False,
                device_id=device.id,
                action=action,
                vendor=device.vendor,
                api_protocol=api.protocol.value,
                latency_ms=latency_ms,
                response={},
                error=error_msg,
                vendor_quirk_triggered=quirk,
            )

        response, quirk = await self._execute(device, action, payload)
        elapsed_ms = (time.monotonic() - start) * 1000

        return RemedyActionResult(
            success=True,
            device_id=device.id,
            action=action,
            vendor=device.vendor,
            api_protocol=api.protocol.value,
            latency_ms=elapsed_ms,
            response=response,
            vendor_quirk_triggered=quirk,
        )

    @abstractmethod
    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        """Execute the action and return (response_dict, quirk_note_or_None)."""

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        return f"API call failed ({device.sku.api.protocol.value})", None

    _rate_limit_tokens: dict[str, tuple[float, int]] = {}

    async def _check_rate_limit(self, device: DeviceInstance, rps: float) -> None:
        key = f"{device.sku.vendor}:{device.id}"
        now = time.monotonic()
        last_time, tokens = self._rate_limit_tokens.get(key, (now, int(rps)))
        elapsed = now - last_time
        tokens = min(int(rps), int(tokens + elapsed * rps))
        if tokens <= 0:
            wait = 1.0 / rps
            await asyncio.sleep(wait)
            tokens = 1
        self._rate_limit_tokens[key] = (now, tokens - 1)


class CiscoIOSXEDriver(VendorAPIDriver):
    """Cisco IOS-XE RESTCONF/YANG driver.

    Response schema: JSON under Cisco IOS-XE native YANG models.
    Different from NX-OS, different from Meraki — even though all are "Cisco".
    """
    protocol = APIProtocol.IOS_XE_RESTCONF

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        quirk = None

        if action == "get_status":
            # Simulate IOS-XE RESTCONF response schema
            response = {
                "Cisco-IOS-XE-native:hostname": device.hostname,
                "Cisco-IOS-XE-native:version": device.firmware_version,
                "Cisco-IOS-XE-memory-oper:memory-statistics": {
                    "memory-statistic": [
                        {
                            "name": "Processor",
                            "total-memory": 4294967296,
                            "used-memory": int(4294967296 * device.metrics.memory_utilization / 100),
                        }
                    ]
                },
                "Cisco-IOS-XE-process-cpu-oper:cpu-usage": {
                    "cpu-utilization": {
                        "five-seconds": round(device.metrics.cpu_utilization, 1),
                        "one-minute": round(device.metrics.cpu_utilization * 0.9, 1),
                        "five-minutes": round(device.metrics.cpu_utilization * 0.85, 1),
                    }
                },
                "ietf-interfaces:interfaces": {
                    "interface": [
                        {"name": f"GigabitEthernet1/{i}", "oper-status": "up"}
                        for i in range(min(4, device.sku.port_count or 4))
                    ]
                },
            }
            # Quirk: version path differs between IOS-XE 16.x and 17.x
            if device.firmware_version.startswith("16."):
                quirk = "IOS-XE 16.x uses different YANG path for version — use Cisco-IOS-XE-native:version only"

        elif action == "reboot":
            # Quirk: HTTP 200 does not confirm reboot — must poll
            response = {
                "Cisco-IOS-XE-rpc:output": {"result": "IOS-XE reboot initiated"},
                "_note": "Poll GET /restconf/data/Cisco-IOS-XE-native:native/hostname to confirm reboot",
            }
            quirk = "HTTP 200 returned before reboot executes — poll uptime to confirm"

        elif action == "get_interfaces":
            response = {
                "ietf-interfaces:interfaces": {
                    "interface": [
                        {
                            "name": f"GigabitEthernet1/{i}",
                            "type": "iana-if-type:ethernetCsmacd",
                            "enabled": True,
                            "oper-status": "up",
                            "statistics": {
                                "in-octets": random.randint(1000000, 9999999999),
                                "out-octets": random.randint(1000000, 9999999999),
                                "in-errors": random.randint(0, 50),
                                "out-errors": random.randint(0, 10),
                            },
                        }
                        for i in range(min(8, device.sku.port_count or 8))
                    ]
                }
            }

        elif action == "get_logs":
            response = {
                "Cisco-IOS-XE-native:logging": {
                    "buffered": {
                        "entries": [
                            f"%{random.choice(['SYS', 'LINK', 'OSPF'])}-{random.randint(1,7)}-"
                            f"{random.choice(['UPDOWN', 'CHANGED', 'ADJ'])}: {device.hostname} event"
                            for _ in range(10)
                        ]
                    }
                }
            }

        else:
            response = {"error": f"Unknown action: {action}"}

        return response, quirk

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        errors = [
            ("409 Conflict: candidate configuration locked by another session", "locked_config"),
            ("401 Unauthorized: basic auth failed — check credentials", None),
            ("503 Service Unavailable: RESTCONF process not running", "restconf_disabled"),
        ]
        return random.choice(errors)


class CiscoMerakiDriver(VendorAPIDriver):
    """Cisco Meraki Dashboard API driver.

    Cloud-managed: ALL calls go through api.meraki.com.
    Rate limit: 5 req/s per ORG (shared — not per device or per key).
    Response schema: JSON but completely different from IOS-XE.
    """
    protocol = APIProtocol.MERAKI_DASHBOARD

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        quirk = None

        if action == "get_status":
            response = {
                # Meraki uses serial, not hostname, as the primary identifier
                "serial": f"Q2{device.id[:4].upper()}-{device.id[4:8].upper()}-{device.id[8:12].upper()}",
                "name": device.hostname,
                "model": device.model,
                "networkId": f"N_{device.location.site_id[:8]}",
                "status": "online" if device.state.value == "healthy" else "alerting",
                "lastReportedAt": "2026-06-14T10:00:00Z",
                "connectionType": "wired",
                "firmware": device.firmware_version,
                "tags": [device.location.site_type, device.location.site_name],
                "lanIp": device.ip_addresses[0] if device.ip_addresses else None,
            }
            quirk = "Meraki identifies devices by serial, not hostname — store serial for subsequent calls"

        elif action == "reboot":
            # Meraki reboot: async — config may not apply for 30-90s
            response = {
                "success": True,
                "_note": "Device reboot queued. Actual reboot may take 30–90s. "
                         "Management plane will go dark during reboot.",
            }
            quirk = "Config change queued — device may not apply for 30–90s; management dark during reboot"

        elif action == "get_clients":
            response = {
                "clients": [
                    {
                        "id": f"k{i}abc{device.id[:4]}",
                        "mac": f"aa:bb:cc:{i:02x}:{i:02x}:{i:02x}",
                        "description": f"Client-{i}",
                        "ip": f"192.168.{i % 10}.{i}",
                        "ssid": "CorpWifi",
                        "rssi": random.randint(-70, -30),
                    }
                    for i in range(min(10, (device.metrics.client_count or 0)))
                ]
            }

        elif action == "get_logs":
            response = {
                "pageStartAt": "2026-06-14T09:00:00Z",
                "pageEndAt": "2026-06-14T10:00:00Z",
                "events": [
                    {
                        "occurredAt": "2026-06-14T09:30:00Z",
                        "networkId": f"N_{device.location.site_id[:8]}",
                        "type": random.choice(["association", "disassociation", "packet_flood"]),
                        "description": f"Client event on {device.hostname}",
                        "deviceSerial": f"Q2{device.id[:4].upper()}",
                    }
                    for _ in range(5)
                ],
            }

        else:
            response = {"errors": [f"Action '{action}' not supported"]}

        return response, quirk

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        errors = [
            ("429 Too Many Requests: rate limit exceeded (5 req/s per org)", "rate_limit_exceeded"),
            ("404 Not Found: device serial not found in organization", "serial_mismatch"),
            ("400 Bad Request: networkId required for this endpoint", "missing_network_id"),
        ]
        return random.choice(errors)


class ArubaOSCXDriver(VendorAPIDriver):
    """Aruba ArubaOS-CX on-box REST driver (for CX switches).

    Session-cookie auth with 30-min TTL — must refresh before expiry.
    """
    protocol = APIProtocol.ARUBA_OS_CX

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        quirk = None

        if action == "get_status":
            response = {
                "product_info": {
                    "product_name": device.model,
                    "serial_number": f"SG{device.id[:8].upper()}",
                    "vendor": "Aruba",
                },
                "system": {
                    "hostname": device.hostname,
                    "software_version": device.firmware_version,
                    "uptime": int(device.metrics.uptime_hours * 3600),
                    "cpu": {
                        "current": round(device.metrics.cpu_utilization, 1),
                    },
                    "memory": {
                        "total": 4294967296,
                        "used": int(4294967296 * device.metrics.memory_utilization / 100),
                    },
                },
            }
            quirk = "ArubaOS-CX API versioned in path (/rest/v10.08/) — pin version or responses differ"

        elif action == "reboot":
            response = {
                "status": "initiated",
                "message": "System reload initiated. Session will disconnect.",
                "_warning": "Session cookie invalidated on reboot — must re-authenticate after",
            }
            quirk = "Session cookie is invalidated by reboot — re-login required; no persistent token"

        elif action == "get_interfaces":
            response = {
                "interfaces": {
                    f"1/{i}": {
                        "admin_state": "up",
                        "link_state": "up",
                        "speed": "1000",
                        "statistics": {
                            "rx_bytes": random.randint(1000, 999999999),
                            "tx_bytes": random.randint(1000, 999999999),
                            "rx_errors": random.randint(0, 10),
                        },
                    }
                    for i in range(1, min(9, (device.sku.port_count or 8) + 1))
                }
            }

        elif action == "get_logs":
            response = {
                "event_log": [
                    {
                        "timestamp": "2026-06-14T09:00:00Z",
                        "severity": random.choice(["INFO", "WARNING", "ERROR"]),
                        "subsystem": random.choice(["MSTP", "OSPF", "FAN", "PSU"]),
                        "message": f"Event on {device.hostname}",
                    }
                    for _ in range(8)
                ]
            }

        else:
            response = {"status": "error", "message": f"Unknown action: {action}"}

        return response, quirk

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        errors = [
            ("401 Unauthorized: session cookie expired — re-authenticate", "session_expired"),
            ("423 Locked: configuration session locked by admin", "config_locked"),
            ("503 Service Unavailable: REST daemon restarting", None),
        ]
        return random.choice(errors)


class ArubaWAPDriver(VendorAPIDriver):
    """Aruba Central cloud driver for WAPs.

    JWT access token expires every 2h — refresh token expires every 14 days.
    """
    protocol = APIProtocol.ARUBA_CENTRAL

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        quirk = None

        if action == "get_status":
            response = {
                "serial": f"AR{device.id[:10].upper()}",
                "status": "Up" if device.state.value == "healthy" else "Down",
                "name": device.hostname,
                "model": device.model,
                "firmware_version": device.firmware_version,
                "uptime": int(device.metrics.uptime_hours * 3600),
                "cpu_utilization": round(device.metrics.cpu_utilization, 1),
                "mem_utilization": round(device.metrics.memory_utilization, 1),
                "client_count": device.metrics.client_count or 0,
                "ip_address": device.ip_addresses[0] if device.ip_addresses else None,
                "group_name": device.location.site_name,
            }
            quirk = "Token expires in 2h — track expiry and refresh before calling again"

        elif action == "reboot":
            response = {
                "task_id": f"task_{device.id[:8]}",
                "status": "queued",
                "message": "AP reboot task queued in Aruba Central. Check task_id for status.",
            }
            quirk = "Reboot is async — poll /monitoring/v1/tasks/{task_id} for completion"

        elif action == "get_clients":
            response = {
                "clients": [
                    {
                        "macaddr": f"aa:{i:02x}:bb:{i:02x}:cc:{i:02x}",
                        "name": f"Client-{i}",
                        "ip_address": f"10.30.{i % 255}.{i % 254 + 1}",
                        "associated_device": device.serial if hasattr(device, "serial") else device.id[:8],
                        "channel": random.choice([1, 6, 11, 36, 40, 44, 48]),
                        "rssi": random.randint(-75, -30),
                        "speed": random.choice([54, 130, 300, 450, 867]),
                    }
                    for i in range(min(10, device.metrics.client_count or 0))
                ],
                "total": device.metrics.client_count or 0,
            }

        elif action == "get_logs":
            response = {
                "alerts": [
                    {
                        "timestamp": "2026-06-14T09:00:00Z",
                        "severity": random.choice(["minor", "major", "critical"]),
                        "category": random.choice(["wids", "client", "device"]),
                        "description": f"Alert on {device.hostname}",
                        "device_serial": f"AR{device.id[:10].upper()}",
                    }
                    for _ in range(5)
                ]
            }

        else:
            response = {"error": f"Unsupported action: {action}"}

        return response, quirk

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        errors = [
            ("401 Unauthorized: access_token expired — use refresh_token to obtain new token", "token_expired"),
            ("429 Too Many Requests: rate limit exceeded (10 req/s)", "rate_limit"),
            ("404 Not Found: device serial not registered in Central", "device_not_found"),
        ]
        return random.choice(errors)


class JuniperNetconfDriver(VendorAPIDriver):
    """Juniper NETCONF/XML driver.

    All responses are XML — no JSON option.
    Must lock candidate config before editing; commit confirmed required.
    """
    protocol = APIProtocol.NETCONF_XML

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        quirk = None

        if action == "get_status":
            # Returns XML — represented here as escaped string since JSON can't contain raw XML
            xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <system-information>
    <host-name>{device.hostname}</host-name>
    <hardware-model>{device.model}</hardware-model>
    <os-version>{device.firmware_version}</os-version>
    <serial-number>JN{device.id[:8].upper()}</serial-number>
    <uptime-information>
      <up-time>
        <seconds>{int(device.metrics.uptime_hours * 3600)}</seconds>
      </up-time>
    </uptime-information>
  </system-information>
</rpc-reply>"""
            response = {
                "_format": "xml",
                "_raw_xml": xml_response,
                "_note": "Parse with lxml or defusedxml — standard json.loads() will NOT work",
                "parsed": {
                    "hostname": device.hostname,
                    "model": device.model,
                    "version": device.firmware_version,
                    "uptime_seconds": int(device.metrics.uptime_hours * 3600),
                },
            }
            quirk = "NETCONF response is XML — parse with lxml; errors are <rpc-error> inside 200 OK"

        elif action == "reboot":
            xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <ok/>
</rpc-reply>"""
            response = {
                "_format": "xml",
                "_raw_xml": xml_response,
                "_note": "commit confirmed: follow-up <commit> within timeout or config auto-rollbacks",
                "parsed": {"status": "ok", "action": "reboot"},
            }
            quirk = "commit confirmed — must send follow-up <commit> within timeout window or rollback fires"

        elif action == "get_interfaces":
            xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <interface-information>
    {''.join(
        f'<physical-interface><name>ge-0/0/{i}</name><oper-status>up</oper-status>'
        f'<input-bps>{random.randint(100, 9999999)}</input-bps>'
        f'<output-bps>{random.randint(100, 9999999)}</output-bps></physical-interface>'
        for i in range(min(8, device.sku.port_count or 8))
    )}
  </interface-information>
</rpc-reply>"""
            response = {
                "_format": "xml",
                "_raw_xml": xml_response,
                "_note": "Interface names use Junos format (ge-0/0/N, xe-0/0/N) — not Cisco format",
            }
            quirk = "Junos interface naming (ge-0/0/0) differs from Cisco (Gi1/0/1) — normalize in parser"

        elif action == "get_logs":
            response = {
                "_format": "xml",
                "_raw_xml": f"""<rpc-reply><log-information>
  <log><name>messages</name>
    <log-entry>
      <log-message>{device.hostname}: interface ge-0/0/0 link-down</log-message>
    </log-entry>
  </log></log-information></rpc-reply>""",
                "parsed": {"entries": [f"{device.hostname}: log entry {i}" for i in range(5)]},
            }

        else:
            response = {"_format": "xml", "_raw_xml": "<rpc-error><error-message>unknown RPC</error-message></rpc-error>"}

        return response, quirk

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        errors = [
            ("lock-denied: configuration locked by session 12345 — wait or force unlock", "config_lock"),
            ("in-use: commit operation in progress — retry after current commit completes", "commit_in_progress"),
            ("SSH connection reset: Junos NETCONF daemon restarted", None),
        ]
        return random.choice(errors)


class PanOSDriver(VendorAPIDriver):
    """Palo Alto PAN-OS XML API driver.

    API key generated via keygen — not the admin password.
    Two-phase commit: edit → commit job → poll job ID.
    All responses are XML.
    """
    protocol = APIProtocol.PAN_OS_XML

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        quirk = None

        if action == "get_status":
            xml_response = f"""<response status="success">
  <result>
    <system>
      <hostname>{device.hostname}</hostname>
      <model>{device.model}</model>
      <sw-version>{device.firmware_version}</sw-version>
      <uptime>{int(device.metrics.uptime_hours // 24)} days, {int(device.metrics.uptime_hours % 24)}:00:00</uptime>
      <serial>PA{device.id[:10].upper()}</serial>
      <operational-mode>normal</operational-mode>
    </system>
  </result>
</response>"""
            response = {
                "_format": "xml",
                "_raw_xml": xml_response,
                "_note": "Must parse XML; status=success in attribute not always reliable — check <result> too",
                "parsed": {
                    "hostname": device.hostname,
                    "model": device.model,
                    "version": device.firmware_version,
                    "uptime_hours": device.metrics.uptime_hours,
                    "serial": f"PA{device.id[:10].upper()}",
                },
            }
            quirk = "PAN-OS XML API: API key != admin password; generate via /api/?type=keygen"

        elif action == "reboot":
            # Two-phase: first send op command, returns job ID
            job_id = random.randint(100, 9999)
            xml_response = f"""<response status="success">
  <result>
    <job>{job_id}</job>
    <message>Reboot job {job_id} queued</message>
  </result>
</response>"""
            response = {
                "_format": "xml",
                "_raw_xml": xml_response,
                "_note": f"Poll job status: GET /api/?type=op&cmd=<show><jobs><id>{job_id}</id></jobs></show>",
                "parsed": {"job_id": job_id, "status": "queued"},
            }
            quirk = f"Reboot is async job {job_id} — poll job status; device may take 3-5 min to come back"

        elif action == "get_sessions":
            response = {
                "_format": "xml",
                "_raw_xml": f"""<response status="success"><result>
  <entry><idx>1</idx><application>web-browsing</application><state>ACTIVE</state>
    <src>{device.ip_addresses[0] if device.ip_addresses else '10.0.0.1'}</src>
    <dst>8.8.8.8</dst></entry>
</result></response>""",
                "parsed": {
                    "total_sessions": random.randint(100, device.sku.max_sessions or 10000),
                    "active": random.randint(50, 5000),
                },
            }

        elif action == "get_logs":
            response = {
                "_format": "xml",
                "_raw_xml": f"""<response status="success"><result>
  <log><logs>
    <entry><time>2026-06-14 09:00:00</time><type>TRAFFIC</type>
      <msg>Session from {device.ip_addresses[0] if device.ip_addresses else '10.0.0.1'}</msg>
    </entry>
  </logs></log>
</result></response>""",
                "parsed": {"entries": [f"Log entry {i}" for i in range(5)]},
            }

        else:
            response = {
                "_format": "xml",
                "_raw_xml": f'<response status="error"><result><msg>Unknown action: {action}</msg></result></response>',
            }

        return response, quirk

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        errors = [
            ("Invalid credentials: API key may have expired — regenerate via keygen endpoint", "api_key_expired"),
            ("Commit lock: another administrator has a commit lock — release or wait", "commit_lock"),
            ("Operation not allowed in current HA state: send to active unit", "ha_state_mismatch"),
        ]
        return random.choice(errors)


class FortiOSDriver(VendorAPIDriver):
    """Fortinet FortiOS REST driver.

    Token-based auth scoped to admin VDOM access.
    VDOM must be specified in URL for multi-VDOM systems.
    """
    protocol = APIProtocol.FORTI_OS_REST

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        quirk = None

        if action == "get_status":
            response = {
                "status": "success",
                "http_status": 200,
                "serial": f"FGT{device.id[:8].upper()}",
                "version": device.firmware_version,
                "results": {
                    "model_name": device.model,
                    "hostname": device.hostname,
                    "uptime": int(device.metrics.uptime_hours * 3600),
                    "cpu": round(device.metrics.cpu_utilization, 1),
                    "mem": round(device.metrics.memory_utilization, 1),
                    "disk": random.randint(10, 60),
                    "net_usage": random.randint(5, 80),
                    "ha_mode": "standalone",
                },
            }
            quirk = "Multi-VDOM: append ?vdom=root or desired VDOM to URL — missing VDOM returns root"

        elif action == "reboot":
            response = {
                "status": "success",
                "http_status": 200,
                "results": {},
                "_warning": "Firmware upgrade API triggers INSTANT reboot — no grace period or confirmation",
            }
            quirk = "Reboot is IMMEDIATE — no async job, no grace period; connection drops instantly"

        elif action == "get_sessions":
            response = {
                "status": "success",
                "results": [
                    {
                        "proto": random.choice(["tcp", "udp"]),
                        "proto_state": "01",
                        "duration": random.randint(1, 3600),
                        "policyid": random.randint(1, 100),
                        "src": f"10.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}",
                        "dst": f"8.8.{random.randint(1, 8)}.{random.randint(1, 8)}",
                    }
                    for _ in range(10)
                ],
                "total": random.randint(10000, 1000000),
            }

        elif action == "get_logs":
            response = {
                "status": "success",
                "results": [
                    {
                        "timestamp": 1718352000 + i * 60,
                        "type": random.choice(["traffic", "event", "ips"]),
                        "level": random.choice(["notice", "warning", "error"]),
                        "msg": f"FortiOS event on {device.hostname}",
                        "devname": device.hostname,
                        "devid": f"FGT{device.id[:8].upper()}",
                    }
                    for i in range(8)
                ],
            }

        else:
            response = {"status": "error", "http_status": 400, "error": f"Unknown action: {action}"}

        return response, quirk

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        errors = [
            ("401: invalid token — token may be scoped to wrong VDOM", "vdom_scope_mismatch"),
            ("500: IPS engine crashed — device rebooting", "ips_crash"),
            ("403: administrator account locked — too many failed auth attempts", "account_locked"),
        ]
        return random.choice(errors)


class DellRedfishDriver(VendorAPIDriver):
    """Dell iDRAC Redfish driver.

    Same Redfish standard as HPE but Dell OEM extensions differ completely.
    iDRAC can lock up while OS runs fine (bmc_lockup failure mode).
    """
    protocol = APIProtocol.DELL_REDFISH

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        quirk = None

        if action == "get_status":
            response = {
                "@odata.context": "/redfish/v1/$metadata#ComputerSystem.ComputerSystem",
                "@odata.id": f"/redfish/v1/Systems/System.Embedded.1",
                "Id": "System.Embedded.1",
                "Name": device.hostname,
                "Model": device.model,
                "Manufacturer": "Dell Inc.",
                "SerialNumber": f"D{device.id[:7].upper()}",
                "BIOSVersion": "2.18.0",
                "PowerState": "On" if device.state.value != "failed" else "Off",
                "Status": {
                    "State": "Enabled",
                    "Health": "OK" if device.state.value == "healthy" else "Warning",
                },
                "ProcessorSummary": {
                    "Count": device.sku.cpu_cores or 32,
                    "Status": {"Health": "OK"},
                },
                "MemorySummary": {
                    "TotalSystemMemoryGiB": device.sku.ram_gb or 256,
                    "Status": {"Health": "OK"},
                },
                "Oem": {
                    "Dell": {
                        "DellSystem": {
                            "SystemID": f"0x{random.randint(0, 65535):04x}",
                            "BIOSReleaseDate": "12/01/2023",
                        }
                    }
                },
            }
            quirk = "Dell OEM extensions under Oem.Dell — incompatible with HPE's Oem.Hpe; parse separately"

        elif action == "reboot":
            job_id = f"JID_{random.randint(100000000, 999999999)}"
            response = {
                "@odata.id": f"/redfish/v1/TaskService/Tasks/{job_id}",
                "TaskState": "Pending",
                "TaskStatus": "OK",
                "Messages": [{"Message": f"Job {job_id} submitted for reboot"}],
                "_note": f"Poll GET /redfish/v1/TaskService/Tasks/{job_id} until TaskState=Completed",
            }
            quirk = f"Dell job queue: must poll task {job_id}; iDRAC response times often exceed 30s"

        elif action == "get_logs":
            response = {
                "@odata.context": "/redfish/v1/$metadata#LogEntryCollection.LogEntryCollection",
                "Members": [
                    {
                        "Id": str(i),
                        "EntryType": "Event",
                        "Severity": random.choice(["OK", "Warning", "Critical"]),
                        "Message": f"Dell iDRAC event on {device.hostname}",
                        "OemRecordFormat": "Dell",
                        "Oem": {"Dell": {"ServiceTag": f"D{device.id[:7].upper()}"}},
                    }
                    for i in range(10)
                ],
            }

        else:
            response = {
                "error": {
                    "code": "Base.1.0.GeneralError",
                    "message": f"Action '{action}' not supported",
                }
            }

        return response, quirk

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        errors = [
            ("iDRAC unresponsive: BMC lockup detected — OS may still be running; try iDRAC reset", "bmc_lockup"),
            ("408 Request Timeout: iDRAC response time exceeded 30s — increase client timeout", "slow_idrac"),
            ("503 Service Unavailable: iDRAC firmware update in progress", None),
        ]
        return random.choice(errors)


class SNMPOnlyDriver(VendorAPIDriver):
    """SNMP-only driver for legacy or consumer devices.

    Read-only, no structured API, vendor MIB required.
    No write capability without SNMPv3 + auth.
    """
    protocol = APIProtocol.SNMP_V2C

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        if action == "get_status":
            response = {
                "1.3.6.1.2.1.1.1.0": f"Hardware: {device.model} Software: {device.firmware_version}",
                "1.3.6.1.2.1.1.3.0": int(device.metrics.uptime_hours * 360000),  # hundredths of seconds
                "1.3.6.1.2.1.1.5.0": device.hostname,
                "_note": "OID values require vendor MIB to decode. Community string must match device config.",
                "parsed": {
                    "sysDescr": f"Hardware: {device.model} Software: {device.firmware_version}",
                    "sysUpTime_hundredths": int(device.metrics.uptime_hours * 360000),
                    "sysName": device.hostname,
                },
            }
            return response, "OID parsing requires vendor MIB; SNMP traps are UDP fire-and-forget — may be missed"

        return {
            "error": f"Action '{action}' not supported via SNMP",
            "_note": "SNMP is read-mostly; write requires SNMPv3 + authPriv; no exec/reboot capability",
        }, "SNMP has no reboot/exec capability — physical access required"


class NoAPIDriver(VendorAPIDriver):
    """No management API — shadow/consumer IT with no remote access."""
    protocol = APIProtocol.NONE

    async def _execute(
        self, device: DeviceInstance, action: str, payload: Optional[dict]
    ) -> tuple[dict, Optional[str]]:
        return {
            "error": "No management interface available",
            "device": device.hostname,
            "vendor": device.vendor,
            "model": device.model,
            "_note": "Physical access required. Dispatch a technician.",
        }, "No remote management — consumer/shadow IT device; only physical access possible"

    def _vendor_error(self, device: DeviceInstance, action: str) -> tuple[str, Optional[str]]:
        return "No management API — physical access only", "no_api"


# ---------------------------------------------------------------------------
# Driver registry — maps protocol → driver class
# ---------------------------------------------------------------------------

_DRIVER_MAP: dict[APIProtocol, type[VendorAPIDriver]] = {
    APIProtocol.IOS_XE_RESTCONF: CiscoIOSXEDriver,
    APIProtocol.NXOS_REST: CiscoIOSXEDriver,        # Similar enough for sim purposes
    APIProtocol.MERAKI_DASHBOARD: CiscoMerakiDriver,
    APIProtocol.ARUBA_OS_CX: ArubaOSCXDriver,
    APIProtocol.ARUBA_CENTRAL: ArubaWAPDriver,
    APIProtocol.NETCONF_XML: JuniperNetconfDriver,
    APIProtocol.PAN_OS_XML: PanOSDriver,
    APIProtocol.FORTI_OS_REST: FortiOSDriver,
    APIProtocol.DELL_REDFISH: DellRedfishDriver,
    APIProtocol.HPE_REDFISH: DellRedfishDriver,     # Same Redfish standard, different OEM
    APIProtocol.SNMP_V2C: SNMPOnlyDriver,
    APIProtocol.SNMP_V3: SNMPOnlyDriver,
    APIProtocol.SSH_CLI: SNMPOnlyDriver,
    APIProtocol.NONE: NoAPIDriver,
}

_driver_instances: dict[APIProtocol, VendorAPIDriver] = {}


def get_driver(device: DeviceInstance) -> VendorAPIDriver:
    protocol = device.sku.api.protocol
    if protocol not in _driver_instances:
        driver_cls = _DRIVER_MAP.get(protocol, NoAPIDriver)
        _driver_instances[protocol] = driver_cls()
    return _driver_instances[protocol]


async def api_call(
    device: DeviceInstance,
    action: str,
    payload: Optional[dict] = None,
) -> RemedyActionResult:
    """Entry point for all vendor API calls. Routes to the right driver automatically."""
    driver = get_driver(device)
    return await driver.call(device, action, payload)
