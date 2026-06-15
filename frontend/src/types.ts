export type DeviceCategory =
  | 'wan_edge' | 'router' | 'switch_core' | 'switch_dist' | 'switch_access'
  | 'firewall' | 'wap' | 'wireless_controller' | 'load_balancer'
  | 'server' | 'storage' | 'endpoint' | 'phone' | 'printer' | 'ups' | 'pdu'

export type DeviceState =
  | 'healthy' | 'degraded' | 'failed' | 'unreachable' | 'recovering' | 'rebooting' | 'maintenance'

export type APIProtocol =
  | 'ios_xe_restconf' | 'nxos_rest' | 'meraki_dashboard' | 'aruba_central' | 'aruba_os_cx'
  | 'netconf_xml' | 'pan_os_xml' | 'forti_os_rest' | 'dell_redfish' | 'hpe_redfish'
  | 'snmp_v2c' | 'snmp_v3' | 'ssh_cli' | 'none'

export interface DeviceLocation {
  site_id: string
  site_name: string
  site_type: 'hq' | 'regional' | 'branch'
  building: string
  floor: number
  rack_id: string | null
  rack_unit: number | null
}

export interface DeviceMetrics {
  cpu_utilization: number
  memory_utilization: number
  uptime_hours: number
  client_count: number | null
  interface_utilization: Record<string, number>
  packets_per_second: number
  error_rate: number
}

export interface FailureModeInfo {
  id: string
  name: string
  severity: string
  description: string
}

export interface Device {
  id: string
  sku_id: string
  hostname: string
  vendor: string
  product_line: string
  model: string
  category: DeviceCategory
  firmware_version: string
  age_years: number
  state: DeviceState
  location: DeviceLocation
  parent_id: string | null
  ip_addresses: string[]
  vlan_ids: number[]
  metrics: DeviceMetrics
  active_failure_modes: string[]
  failure_count_24h: number
  last_failure_at: string | null
  api_protocol: APIProtocol
  is_manually_failed: boolean
  is_consumer_grade: boolean
  children_ids: string[]
  available_failure_modes: FailureModeInfo[]
}

export interface Site {
  id: string
  name: string
  site_type: 'hq' | 'regional' | 'branch'
  city: string
  state_code: string
  employee_count: number
  device_ids: string[]
  device_count?: number
  healthy_count?: number
  impaired_count?: number
}

export interface Alert {
  id: string
  timestamp: string
  sim_time: string
  event_type: string
  device_id: string
  hostname: string
  vendor: string
  site_name: string
  failure_mode_id: string | null
  severity: 'low' | 'medium' | 'high' | 'critical'
  message: string
  is_manual: boolean
  cascade_from_device_id: string | null
  previous_state: string | null
  new_state: string | null
}

export interface WorldSummary {
  id: string
  seed: number
  org_name: string
  sim_time: string
  sim_speed: number
  is_running: boolean
  total_devices: number
  healthy_count: number
  degraded_count: number
  failed_count: number
  unreachable_count: number
  rebooting_count: number
  total_sites: number
  active_alerts: number
  global_failure_multiplier: number
  tick_count: number
}

export interface TopologyNode {
  id: string
  label: string
  category: DeviceCategory
  state: DeviceState
  vendor: string
  site_id: string
  site_name: string
  parent_id: string | null
  is_consumer_grade: boolean
}

export interface TopologyEdge {
  source: string
  target: string
  link_type: string
}

export interface TopologyData {
  nodes: TopologyNode[]
  edges: TopologyEdge[]
}

export interface APICallResult {
  success: boolean
  device_id: string
  action: string
  vendor: string
  api_protocol: string
  latency_ms: number
  response: Record<string, unknown>
  error: string | null
  vendor_quirk_triggered: string | null
}

export type WSMessage =
  | { type: 'world_snapshot'; data: { summary: WorldSummary; devices: Device[]; sites: Site[]; topology: TopologyData } }
  | { type: 'device_update'; data: Device }
  | { type: 'alert'; data: Alert }
  | { type: 'tick'; data: WorldSummary }
  | { type: 'ping' }
  | { type: 'pong' }

// ---------------------------------------------------------------------------
// Remediation engine types (standalone service)
// ---------------------------------------------------------------------------

export interface RemediationAction {
  id: string
  created_at: string
  rule_id: string | null
  agent_type: 'rules' | 'ml' | 'llm'
  device_id: string
  hostname: string
  site_name: string
  action_type: 'reboot' | 'maintenance_on' | 'maintenance_off' | 'alert'
  reason: string
  severity: string
  auto_execute: boolean
  status: 'pending' | 'approved' | 'auto' | 'rejected' | 'executing' | 'done' | 'failed'
  approved_by: string | null
  executed_at: string | null
  result: string | null
}

export interface AgentThought {
  id: string
  timestamp: string
  content: string
  is_complete: boolean
  actions_proposed: string[]
}

export interface RemediationConfig {
  human_in_loop: boolean
  rules_enabled: boolean
  ml_enabled: boolean
  llm_enabled: boolean
  llm_auto_trigger: boolean
  rules_status: Record<string, boolean>
}

export interface RuleDefinition {
  id: string
  name: string
  description: string
  severity: string
  action_type: string
  auto_execute: boolean
  cooldown_ticks: number
  enabled: boolean
}

export type RemediationWSMessage =
  | { type: 'snapshot'; data: { config: RemediationConfig; rules: RuleDefinition[]; actions: RemediationAction[]; agent: Record<string, unknown>; risk_scores: Record<string, number>; source_url: string } }
  | { type: 'action'; data: RemediationAction }
  | { type: 'ml_scores'; data: Record<string, number> }
  | { type: 'agent_thought'; data: AgentThought }
  | { type: 'config'; data: RemediationConfig }
  | { type: 'ping' }
  | { type: 'pong' }
